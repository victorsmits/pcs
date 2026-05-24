"""
cycling/scraper.py — PCS (procyclingstats.com) scraping layer.

Public API
----------
get_soup(url, live=False)                → BeautifulSoup | None
sync_races_year(year)                    → int   (count saved)
sync_race(slug, year, live=False)        → Race | None
sync_stages(race, live=False)            → list[Stage]
sync_stage_results(race, stage, live=False) → list[RaceResult]
sync_rankings(year)                      → int   (count saved)
sync_team(slug, year)                    → Team | None
find_ongoing_races()                     → QuerySet[Race]
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime
from typing import Optional

from bs4 import BeautifulSoup
from django.core.cache import cache
from django.db.models import QuerySet
from django.utils.text import slugify

logger = logging.getLogger(__name__)

PCS_BASE_URL = "https://www.procyclingstats.com"

# ── Cache TTLs ────────────────────────────────────────────────────────────────
_TTL_HISTORICAL = 3600   # 1 hour for finished events
_TTL_LIVE       = 60     # 1 minute for live race data

# ── Session state ─────────────────────────────────────────────────────────────
_session = None
_backend: Optional[str] = None   # 'curl_cffi' | 'cloudscraper' | 'requests'

# ── HTTP headers ──────────────────────────────────────────────────────────────
_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": PCS_BASE_URL + "/",
}

# ── Domain knowledge ──────────────────────────────────────────────────────────
_GRAND_TOUR_SLUGS = frozenset({
    "tour-de-france",
    "giro-d-italia",
    "vuelta-a-espana",
    "tour-de-france-femmes-avec-zwift",
})

_MONUMENT_SLUGS = frozenset({
    "milano-sanremo",
    "ronde-van-vlaanderen",
    "paris-roubaix",
    "liege-bastogne-liege",
    "il-lombardia",
})

# PCS circuits to scrape for the race list
_RACE_CIRCUITS = [
    ("1",  "UCI World Tour"),
    ("26", "UCI ProSeries"),
    ("2",  "UCI World Championships"),
]

# PCS 2-letter flag code → ISO 3166-1 alpha-3 / IOC code used in models
_FLAG2_TO_NAT3: dict[str, str] = {
    "af": "AFG", "al": "ALB", "dz": "DZA", "ad": "AND", "ar": "ARG",
    "am": "ARM", "au": "AUS", "at": "AUT", "az": "AZE", "be": "BEL",
    "by": "BLR", "bo": "BOL", "br": "BRA", "bg": "BGR", "cm": "CMR",
    "ca": "CAN", "cl": "CHL", "cn": "CHN", "co": "COL", "cr": "CRI",
    "hr": "HRV", "cu": "CUB", "cz": "CZE", "dk": "DNK", "ec": "ECU",
    "eg": "EGY", "er": "ERI", "ee": "EST", "et": "ETH", "fi": "FIN",
    "fr": "FRA", "gb": "GBR", "ge": "GEO", "de": "DEU", "gh": "GHA",
    "gr": "GRC", "gt": "GTM", "hu": "HUN", "is": "ISL", "in": "IND",
    "ir": "IRI", "ie": "IRL", "il": "ISR", "it": "ITA", "jm": "JAM",
    "jp": "JPN", "kz": "KAZ", "ke": "KEN", "lv": "LAT", "lt": "LTU",
    "lu": "LUX", "mx": "MEX", "md": "MDA", "mc": "MON", "ma": "MAR",
    "nl": "NLD", "nz": "NZL", "no": "NOR", "pa": "PAN", "pe": "PER",
    "pl": "POL", "pt": "PRT", "ro": "ROU", "ru": "RUS", "rw": "RWA",
    "sa": "SAU", "sk": "SVK", "si": "SVN", "za": "RSA", "kr": "KOR",
    "es": "ESP", "se": "SWE", "ch": "CHE", "tw": "TPE", "tj": "TJK",
    "tr": "TUR", "ua": "UKR", "us": "USA", "uy": "URY", "uz": "UZB",
    "ve": "VEN", "at": "AUT", "ba": "BIH", "cy": "CYP", "dk": "DNK",
    "mk": "MKD", "me": "MNE", "rs": "SRB", "lk": "LKA", "th": "THA",
    "id": "IDN", "my": "MYS", "ph": "PHL", "vn": "VNM", "ng": "NGA",
    "tz": "TZA", "ug": "UGA", "zm": "ZMB", "zw": "ZWE",
}

# Regex helpers
_RE_ORDINAL_PREFIX = re.compile(r"^\d+(st|nd|rd|th)\s*", re.IGNORECASE)
_RE_CLASS_SUFFIX   = re.compile(r"\s*\([^)]*\)\s*$")
_RE_EDITION_SUFFIX = re.compile(r"\s*\[?\d+(st|nd|rd|th)\]?\s*$", re.IGNORECASE)
_RE_YEAR_PREFIX    = re.compile(r"^\d{4}\s*")
_RE_DIST           = re.compile(r"(\d+(?:[.,]\d+)?)")


# ─────────────────────────────────────────────────────────────────────────────
# Session management
# ─────────────────────────────────────────────────────────────────────────────

def _get_session():
    """Return an HTTP session. Tries curl_cffi → cloudscraper → requests."""
    global _session, _backend

    if _session is not None:
        return _session

    # 1. curl_cffi — best TLS/JA3 fingerprint, impersonate a real browser
    try:
        from curl_cffi.requests import Session as CurlSession
        _session = CurlSession(impersonate="chrome124", headers=_HEADERS)
        _backend = "curl_cffi"
        logger.info("PCS scraper: using curl_cffi (chrome124) backend")
        return _session
    except (ImportError, Exception) as exc:
        logger.debug("curl_cffi unavailable: %s", exc)

    # 2. cloudscraper — JS challenge bypass via headless browser simulation
    try:
        import cloudscraper
        _session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False},
            delay=3,
        )
        _session.headers.update(_HEADERS)
        _backend = "cloudscraper"
        logger.info("PCS scraper: using cloudscraper backend")
        return _session
    except (ImportError, Exception) as exc:
        logger.debug("cloudscraper unavailable: %s", exc)

    # 3. Plain requests — last resort; Cloudflare will likely block, but worth trying
    import requests
    _session = requests.Session()
    _session.headers.update(_HEADERS)
    _backend = "requests"
    logger.warning("PCS scraper: using plain requests backend (Cloudflare bypass unlikely)")
    return _session


def _reset_session() -> None:
    """Discard the current session so _get_session() rebuilds it from scratch."""
    global _session, _backend
    _session = None
    _backend = None
    logger.info("PCS scraper: session reset")


# ─────────────────────────────────────────────────────────────────────────────
# Core HTTP helper
# ─────────────────────────────────────────────────────────────────────────────

def get_soup(url: str, live: bool = False) -> Optional[BeautifulSoup]:
    """Fetch a PCS URL and return a parsed BeautifulSoup object.

    Cache behaviour:
    - live=False  → use cache with TTL=_TTL_HISTORICAL (3600 s)
    - live=True   → skip cache, store with TTL=_TTL_LIVE (60 s)
    """
    ttl = _TTL_LIVE if live else _TTL_HISTORICAL
    cache_key = f"pcs_html__{url}"

    if not live:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    session = _get_session()
    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            # Polite delay — slightly longer on retries
            time.sleep(1.0 + attempt * 1.5)
            response = session.get(url, timeout=25)
            if response.status_code == 404:
                logger.debug("404 for %s", url)
                return None
            if response.status_code == 403:
                logger.info("403 on attempt %d/%d for %s — resetting session", attempt + 1, max_attempts, url)
                _reset_session()
                session = _get_session()
                continue
            response.raise_for_status()

            text = response.text
            if not text or len(text) < 500:
                logger.debug("Empty/tiny response for %s (%d bytes)", url, len(text))
                return None

            soup = BeautifulSoup(text, "lxml")

            # Cloudflare challenge pages have <title>Just a moment...</title>
            title_tag = soup.find("title")
            if title_tag and "just a moment" in title_tag.get_text(strip=True).lower():
                logger.warning("Cloudflare challenge on attempt %d/%d for %s", attempt + 1, max_attempts, url)
                _reset_session()
                session = _get_session()
                continue

            cache.set(cache_key, soup, ttl)
            return soup

        except Exception as exc:
            msg = str(exc)
            if "403" in msg and attempt < max_attempts - 1:
                logger.info("403 exception on attempt %d/%d for %s", attempt + 1, max_attempts, url)
                _reset_session()
                session = _get_session()
                continue
            if "404" not in msg and "500" not in msg:
                logger.warning("Failed to fetch %s (attempt %d): %s", url, attempt + 1, exc)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Flag / nationality helpers
# ─────────────────────────────────────────────────────────────────────────────

def _flag2_to_nat3(flag_cls: str) -> str:
    """Convert a 2-letter PCS flag class to a 3-letter model nationality code."""
    return _FLAG2_TO_NAT3.get(flag_cls.lower(), flag_cls.upper()[:3])


def _extract_flag_nat(element) -> str:
    """Return 3-letter nationality from the first .flag span inside *element*."""
    flag = element.find("span", class_="flag") if element else None
    if not flag:
        return ""
    classes = [c for c in flag.get("class", []) if c != "flag"]
    if not classes:
        return ""
    return _flag2_to_nat3(classes[0])


# ─────────────────────────────────────────────────────────────────────────────
# Name cleaning
# ─────────────────────────────────────────────────────────────────────────────

def _clean_race_name(raw: str) -> str:
    name = raw.replace("\xa0", " ").replace("»", "").replace("›", "").strip()
    name = _RE_YEAR_PREFIX.sub("", name).strip()
    name = _RE_ORDINAL_PREFIX.sub("", name).strip()
    name = _RE_CLASS_SUFFIX.sub("", name).strip()
    name = _RE_EDITION_SUFFIX.sub("", name).strip()
    return name.strip(" -|")


# ─────────────────────────────────────────────────────────────────────────────
# Rider / Team getters (shared DB-side helpers)
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create_rider(slug: str, name: str, nat3: str = ""):
    """get_or_create a Rider; update nationality if missing."""
    from cycling.models import Rider
    rider, created = Rider.objects.get_or_create(
        slug=slug,
        defaults={"name": name, "nationality": nat3},
    )
    if not created and nat3 and not rider.nationality:
        rider.nationality = nat3
        rider.save(update_fields=["nationality"])
    return rider


def _resolve_team_from_href(href: str, year: int):
    """Parse a PCS team href like 'team/ineos-grenadiers-2025' and return Team or None."""
    from cycling.models import Team
    href = href.lstrip("/")
    if not href.startswith("team/"):
        return None
    raw = href[5:]   # e.g. "ineos-grenadiers-2025"
    # Strip the trailing -YEAR (4 digits)
    m = re.match(r"^(.+)-(\d{4})$", raw)
    if m:
        team_slug, team_year = m.group(1), int(m.group(2))
    else:
        team_slug = raw
        team_year = year
    return (
        Team.objects.filter(slug=team_slug, year=team_year).first()
        or Team.objects.filter(slug=team_slug).order_by("-year").first()
    )


# ─────────────────────────────────────────────────────────────────────────────
# Results table parser (shared by GC, stage-result, 1-day result)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_results_table(soup: BeautifulSoup, race, stage=None, result_type: str = "gc") -> list:
    """Parse a PCS results table and upsert RaceResult rows.

    Returns a list of RaceResult model instances.
    """
    from cycling.models import RaceResult

    table = soup.find("table", class_="results")
    if not table:
        logger.debug("No .results table found for %s (result_type=%s)", race, result_type)
        return []

    saved: list = []
    winner_rider = None
    winner_team = None

    for row in table.select("tbody tr"):
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        rank_text = cols[0].get_text(strip=True)
        dnf = dns = dsq = False
        rank = None

        if rank_text.isdigit():
            rank = int(rank_text)
        elif rank_text.upper() == "DNF":
            dnf = True
        elif rank_text.upper() == "DNS":
            dns = True
        elif rank_text.upper() in ("DSQ", "DQ"):
            dsq = True
        else:
            # Some rows are section headers or blank — skip
            continue

        # ── Rider ──────────────────────────────────────────────────────────
        rider_td = row.find("td", class_="ridername")
        if not rider_td:
            rider_a = row.find("a", href=re.compile(r"rider/"))
            rider_td = rider_a.parent if rider_a else None
        if not rider_td:
            continue

        rider_link = rider_td.find("a", href=re.compile(r"rider/"))
        if not rider_link:
            continue

        rider_href = rider_link.get("href", "").lstrip("/")
        rider_slug = rider_href[6:] if rider_href.startswith("rider/") else rider_href
        rider_slug = rider_slug.split("/")[0]   # strip any trailing path segment
        rider_name = rider_link.get_text(strip=True)
        nat3 = _extract_flag_nat(rider_td)

        if not rider_slug or not rider_name:
            continue

        rider = _get_or_create_rider(rider_slug, rider_name, nat3)

        # ── Team ───────────────────────────────────────────────────────────
        team_obj = None
        team_link = row.find("a", href=re.compile(r"team/"))
        if team_link:
            team_obj = _resolve_team_from_href(team_link.get("href", ""), race.year)

        # ── Time / gap ─────────────────────────────────────────────────────
        time_gap = ""
        for td in cols:
            classes = " ".join(td.get("class", []))
            text = td.get_text(strip=True)
            # PCS marks time columns with 'time', 'fs11', or the text has +/- prefix
            if ("time" in classes or "fs11" in classes) and text and text not in ("-", ""):
                time_gap = text
                break
        if not time_gap:
            # Fallback: pick any td whose text starts with + (gap) or contains ':'
            for td in cols:
                t = td.get_text(strip=True)
                if t.startswith("+") or (re.match(r"\d+:\d+", t) and rank and rank > 1):
                    time_gap = t
                    break

        # ── Points ─────────────────────────────────────────────────────────
        points = 0.0
        for td in cols:
            t = td.get_text(strip=True)
            # Points are numeric, not time-formatted
            if re.match(r"^\d+$", t) and ":" not in t:
                try:
                    pts = float(t)
                    if pts > 0:
                        points = pts
                        break
                except ValueError:
                    pass

        # ── Upsert RaceResult ──────────────────────────────────────────────
        result, _ = RaceResult.objects.update_or_create(
            rider=rider,
            race=race,
            stage=stage,
            result_type=result_type,
            year=race.year,
            defaults={
                "rank": rank,
                "team": team_obj,
                "time_gap": time_gap[:20],
                "points": points,
                "dnf": dnf,
                "dns": dns,
                "dsq": dsq,
                "is_stage": stage is not None,
            },
        )
        saved.append(result)

        if rank == 1 and not winner_rider:
            winner_rider = rider
            winner_team = team_obj

    # Update winner on race or stage
    if winner_rider:
        if stage is not None:
            stage.__class__.objects.filter(pk=stage.pk).update(
                winner=winner_rider,
                winner_team=winner_team,
            )
        elif result_type in ("gc", "stage"):
            race.__class__.objects.filter(pk=race.pk).update(
                winner=winner_rider,
                winner_team=winner_team,
            )

    return saved


# ─────────────────────────────────────────────────────────────────────────────
# Race list parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date_dd_mm(text: str, year: int) -> Optional[date]:
    """Parse 'DD.MM' date strings common in PCS tables."""
    text = text.strip()
    if not text or "." not in text:
        return None
    parts = text.split(".")
    try:
        return datetime(year, int(parts[1]), int(parts[0])).date()
    except (ValueError, IndexError):
        return None


def _parse_races_list_soup(soup: BeautifulSoup, year: int, circuit_name: str) -> int:
    """Parse a race-list page and upsert Race objects. Returns count saved."""
    from cycling.models import Race

    table = soup.find("table", class_="basic")
    if not table:
        logger.debug("No .basic table in race list for %s", year)
        return 0

    saved = 0
    for row in table.select("tbody tr"):
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        # Find the cell containing the race link
        name_link = None
        name_col = None
        for col in cols:
            a = col.find("a", href=re.compile(r"race/"))
            if a:
                name_link = a
                name_col = col
                break
        if not name_link:
            continue

        name = _clean_race_name(name_link.get_text(strip=True))
        href = name_link.get("href", "").lstrip("/")
        # href may be 'race/slug/year' or 'race/slug/year/gc'
        href_parts = href.split("/")
        if len(href_parts) < 2:
            continue
        race_slug = href_parts[1]

        # Country from flag span in the name column
        country3 = _extract_flag_nat(name_col)

        # Classification is in the last td
        classification = cols[-1].get_text(strip=True)[:10] if cols else ""

        # Date range: cols[0] e.g. '03.07 - 25.07' or '03.07'
        date_range_text = cols[0].get_text(strip=True) if cols else ""
        start_date = end_date = None

        # cols[1] is often the start date alone in DD.MM format
        if len(cols) > 1:
            start_date = _parse_date_dd_mm(cols[1].get_text(strip=True), year)

        # Parse end date from date_range cols[0]
        if " - " in date_range_text:
            end_raw = date_range_text.split(" - ")[-1].strip()
            end_date = _parse_date_dd_mm(end_raw, year)
        elif date_range_text:
            end_date = _parse_date_dd_mm(date_range_text.split()[0], year)

        if not start_date and date_range_text:
            start_raw = date_range_text.split(" - ")[0].strip()
            start_date = _parse_date_dd_mm(start_raw, year)

        if not end_date:
            end_date = start_date

        is_stage_race = classification.startswith("2.")

        Race.objects.update_or_create(
            slug=race_slug,
            year=year,
            defaults={
                "name": name,
                "classification": classification,
                "circuit": circuit_name[:50],
                "country": country3,
                "start_date": start_date,
                "end_date": end_date,
                "is_grand_tour": race_slug in _GRAND_TOUR_SLUGS,
                "is_monument": race_slug in _MONUMENT_SLUGS,
                "is_stage_race": is_stage_race,
            },
        )
        saved += 1

    return saved


# ─────────────────────────────────────────────────────────────────────────────
# Race detail page parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_race_detail_soup(soup: BeautifulSoup, slug: str, year: int) -> dict:
    """Extract race metadata from a PCS race detail page."""
    data: dict = {
        "year": year,
        "pcs_url": f"{PCS_BASE_URL}/race/{slug}/{year}",
        "is_grand_tour": slug in _GRAND_TOUR_SLUGS,
        "is_monument": slug in _MONUMENT_SLUGS,
    }

    try:
        h1 = soup.find("h1")
        if h1:
            raw = h1.get_text(strip=True).replace(str(year), "").strip()
            data["name"] = _clean_race_name(raw) or slug.replace("-", " ").title()
        else:
            data["name"] = slug.replace("-", " ").title()

        for li in soup.find_all("li"):
            title_div = li.find("div", class_="title")
            value_div = li.find("div", class_="value")
            if not title_div or not value_div:
                continue
            key = title_div.get_text(strip=True).lower().rstrip(":").strip()
            val = value_div.get_text(strip=True)
            if not val:
                continue

            if key == "classification":
                data["classification"] = val[:10]
                data["is_stage_race"] = val.startswith("2.")
            elif key == "distance":
                m = _RE_DIST.search(val)
                if m:
                    try:
                        data["distance"] = float(m.group(1).replace(",", "."))
                    except ValueError:
                        pass
            elif key in ("country", "nation", "country of origin"):
                data["country_name"] = val
            elif key == "departure":
                data["departure_city"] = val[:100]
            elif key == "arrival":
                data["arrival_city"] = val[:100]
            elif key in ("startdate", "start date", "date"):
                parts = val.split(".")
                if len(parts) >= 3:
                    try:
                        data["start_date"] = datetime(int(parts[2]), int(parts[1]), int(parts[0])).date()
                    except ValueError:
                        pass
            elif key in ("enddate", "end date"):
                parts = val.split(".")
                if len(parts) >= 3:
                    try:
                        data["end_date"] = datetime(int(parts[2]), int(parts[1]), int(parts[0])).date()
                    except ValueError:
                        pass
            elif key in ("stages", "etapes", "étapes"):
                m = re.search(r"\d+", val)
                if m:
                    try:
                        data["stages_count"] = int(m.group())
                    except ValueError:
                        pass

        # Profile image
        profile_img = soup.find("img", src=lambda s: s and "profile" in s.lower())
        if profile_img:
            src = profile_img.get("src", "")
            data["profile_url"] = src if src.startswith("http") else f"{PCS_BASE_URL}/{src.lstrip('/')}"

        # Flag in header — race country
        header = soup.find("div", class_=re.compile(r"(race-header|page-title|main-title)"))
        if header:
            nat = _extract_flag_nat(header)
            if nat:
                data["country"] = nat

    except Exception as exc:
        logger.error("Error parsing race detail %s/%s: %s", slug, year, exc)

    return data


# ─────────────────────────────────────────────────────────────────────────────
# Stage list parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_stage_type(text: str) -> str:
    t = text.lower()
    if "prologue" in t:
        return "prologue"
    if "cobble" in t or "pavé" in t:
        return "cobbles"
    if "ttt" in t or "team time" in t:
        return "ttt"
    if "itt" in t or "individual time" in t:
        return "itt"
    if "tt" in t or "time trial" in t or "contre-la-montre" in t:
        return "tt"
    if "mountain" in t or "montagne" in t:
        return "mountain"
    if "hilly" in t or "vallonné" in t:
        return "hilly"
    return "flat"


def _parse_stages_soup(soup: BeautifulSoup, race) -> list:
    """Parse a /stages page and upsert Stage objects. Returns list of Stage."""
    from cycling.models import Stage

    stages = []
    for row in soup.select("table.results tbody tr, table.basic tbody tr"):
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        stage_link = row.find("a", href=re.compile(r"/stage-\d+"))
        if not stage_link:
            continue

        href = stage_link.get("href", "")
        m = re.search(r"/stage-(\d+)", href)
        if not m:
            continue
        stage_num = int(m.group(1))

        date_obj = _parse_date_dd_mm(cols[0].get_text(strip=True), race.year)
        dep = cols[1].get_text(strip=True)[:100] if len(cols) > 1 else ""
        arr = cols[2].get_text(strip=True)[:100] if len(cols) > 2 else ""

        dist = None
        if len(cols) > 3:
            dm = _RE_DIST.search(cols[3].get_text(strip=True))
            if dm:
                try:
                    dist = float(dm.group(1).replace(",", "."))
                except ValueError:
                    pass

        stage_type = "flat"
        if len(cols) > 4:
            # cols[4] is the profile icon; check alt text or class
            type_td = cols[4]
            icon = type_td.find("img")
            type_text = (
                (icon.get("alt", "") or icon.get("title", "") or "") if icon
                else type_td.get_text(strip=True)
            )
            stage_type = _parse_stage_type(type_text)

        # Winner is in a rider link anywhere in the row (not the stage link)
        winner_obj = None
        for a in row.find_all("a", href=re.compile(r"rider/")):
            rider_href = a.get("href", "").lstrip("/")
            rider_slug = rider_href[6:].split("/")[0] if rider_href.startswith("rider/") else None
            if rider_slug:
                rider_name = a.get_text(strip=True)
                winner_obj = _get_or_create_rider(rider_slug, rider_name)
                break

        stage, _ = Stage.objects.update_or_create(
            race=race,
            number=stage_num,
            defaults={
                "date": date_obj,
                "departure": dep,
                "arrival": arr,
                "distance": dist,
                "stage_type": stage_type,
                "winner": winner_obj,
            },
        )
        stages.append(stage)

    return stages


# ─────────────────────────────────────────────────────────────────────────────
# Rankings parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_rankings_page(soup: BeautifulSoup, year: int) -> int:
    """Parse one PCS rankings page and upsert Rider objects.

    Returns number of entries processed.
    """
    from cycling.models import Rider, Team

    table = soup.find("table", class_=re.compile(r"results|basic"))
    if not table:
        return 0

    count = 0
    for row in table.select("tbody tr"):
        cols = row.find_all("td")
        if len(cols) < 4:
            continue

        rank_text = cols[0].get_text(strip=True)
        if not rank_text.isdigit():
            continue
        rank = int(rank_text)

        prev_rank = None
        prev_text = cols[1].get_text(strip=True) if len(cols) > 1 else ""
        if prev_text.isdigit():
            prev_rank = int(prev_text)

        rider_td = row.find("td", class_="ridername")
        if not rider_td:
            rider_a = row.find("a", href=re.compile(r"rider/"))
            rider_td = rider_a.parent if rider_a else None
        if not rider_td:
            continue

        rider_link = rider_td.find("a", href=re.compile(r"rider/"))
        if not rider_link:
            continue

        rider_href = rider_link.get("href", "").lstrip("/")
        rider_slug = rider_href[6:].split("/")[0] if rider_href.startswith("rider/") else None
        rider_name = rider_link.get_text(strip=True)
        if not rider_slug or not rider_name:
            continue

        nat3 = _extract_flag_nat(rider_td)
        rider = _get_or_create_rider(rider_slug, rider_name, nat3)

        # Points — rightmost numeric td
        points = 0.0
        for td in reversed(cols):
            t = td.get_text(strip=True).replace(",", "").replace(".", "")
            if re.match(r"^\d+$", t) and int(t) > 0:
                try:
                    points = float(td.get_text(strip=True).replace(",", ""))
                except ValueError:
                    pass
                break

        # Team
        team_obj = None
        team_link = row.find("a", href=re.compile(r"team/"))
        if team_link:
            team_obj = _resolve_team_from_href(team_link.get("href", ""), year)

        current_year = date.today().year
        if year == current_year:
            Rider.objects.filter(pk=rider.pk).update(
                pcs_rank=rank,
                pcs_points=int(points),
            )

        count += 1

    return count


# ─────────────────────────────────────────────────────────────────────────────
# Team parsing
# ─────────────────────────────────────────────────────────────────────────────

_COUNTRY_SLUG_TO_NAT3: dict[str, str] = {
    "belgium": "BEL", "france": "FRA", "italy": "ITA", "spain": "ESP",
    "netherlands": "NLD", "great-britain": "GBR", "germany": "DEU",
    "australia": "AUS", "united-states": "USA", "switzerland": "CHE",
    "denmark": "DNK", "norway": "NOR", "sweden": "SWE", "colombia": "COL",
    "slovenia": "SVN", "poland": "POL", "portugal": "PRT", "kazakhstan": "KAZ",
    "lithuania": "LTU", "latvia": "LAT", "estonia": "EST", "slovakia": "SVK",
    "czech-republic": "CZE", "austria": "AUT", "luxembourg": "LUX",
    "south-africa": "RSA", "new-zealand": "NZL", "canada": "CAN",
    "argentina": "ARG", "ecuador": "ECU", "eritrea": "ERI", "rwanda": "RWA",
    "ukraine": "UKR", "russia": "RUS", "japan": "JPN", "china": "CHN",
    "israel": "ISR", "bahrain": "BHR", "uae": "UAE", "ireland": "IRL",
    "romania": "ROU", "hungary": "HUN", "croatia": "HRV",
}

_TEAM_STATUS_MAP = {
    "WT":  "WorldTeam",
    "PT":  "ProTeam",
    "CT":  "Continental",
    "WWT": "Women",
    "PC":  "ProTeam",
}


def _parse_team_page_soup(soup: BeautifulSoup, slug: str, year: int) -> dict:
    data: dict = {
        "year": year,
        "pcs_url": f"{PCS_BASE_URL}/team/{slug}-{year}",
    }
    try:
        h1 = soup.find("h1")
        if h1:
            data["name"] = h1.get_text(strip=True).replace(str(year), "").strip()
        else:
            data["name"] = slug.replace("-", " ").title()

        img = soup.find("img", class_="teamlogo")
        if img and img.get("src"):
            src = img["src"]
            data["logo_url"] = src if src.startswith("http") else PCS_BASE_URL + src

        for li in soup.select("ul.infolist li"):
            title_div = li.find("div", class_="title")
            value_div = li.find("div", class_="value")
            if not title_div or not value_div:
                continue
            key = title_div.get_text(strip=True).lower().rstrip(":").strip()
            val = value_div.get_text(strip=True)
            link = value_div.find("a", href=True)

            if "status" in key or "team status" in key:
                data["status"] = _TEAM_STATUS_MAP.get(val.strip(), val.strip()[:20])
            elif "abbreviation" in key:
                data["abbreviation"] = val[:10]
            elif "country" in key or "license" in key or "nation" in key:
                data["country_name"] = val
                if link:
                    cs = link.get("href", "").split("/")[-1]
                    data["nationality"] = _COUNTRY_SLUG_TO_NAT3.get(cs.lower(), cs.upper()[:3])
            elif "bike" in key:
                data["bike_brand"] = val[:100]
            elif "clothing" in key or "kit" in key:
                data["clothing_brand"] = val[:100]
            elif "manager" in key or "directeur" in key:
                data["manager"] = val[:200]
            elif "website" in key or "web" in key:
                if link:
                    data["website"] = link.get("href", "")[:200]

    except Exception as exc:
        logger.error("Error parsing team page %s/%s: %s", slug, year, exc)
    return data


def _save_team_roster(team, soup: BeautifulSoup) -> None:
    """Parse rider links on a team page and link each Rider to the team."""
    from cycling.models import Rider

    seen: set[str] = set()
    for a in soup.find_all("a", href=re.compile(r"rider/")):
        href = a.get("href", "").lstrip("/")
        if not href.startswith("rider/"):
            continue
        rider_slug = href[6:].split("/")[0]
        rider_name = a.get_text(strip=True)
        if not rider_slug or not rider_name or rider_slug in seen:
            continue
        seen.add(rider_slug)

        nat3 = ""
        flag = a.find_previous_sibling("span", class_="flag") or a.find_next_sibling("span", class_="flag")
        if flag:
            classes = [c for c in flag.get("class", []) if c != "flag"]
            if classes:
                nat3 = _flag2_to_nat3(classes[0])

        rider = _get_or_create_rider(rider_slug, rider_name, nat3)
        Rider.objects.filter(pk=rider.pk).update(current_team=team)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def sync_races_year(year: int) -> int:
    """Fetch WorldTour + ProSeries + WorldChampionships race lists for *year*.

    Returns the total number of Race objects saved/updated.
    """
    total = 0
    for circuit_id, circuit_name in _RACE_CIRCUITS:
        url = (
            f"{PCS_BASE_URL}/races.php"
            f"?year={year}&circuit={circuit_id}&class=&filter=Filter"
        )
        soup = get_soup(url)
        if soup:
            n = _parse_races_list_soup(soup, year, circuit_name)
            total += n
            logger.info("sync_races_year: %d races saved for circuit=%s year=%d", n, circuit_id, year)
        else:
            logger.warning("sync_races_year: could not fetch circuit=%s year=%d", circuit_id, year)
    return total


def sync_race(slug: str, year: int, live: bool = False):
    """Fetch a race detail page and persist metadata + GC/result data.

    Tries /gc first, then /result, then bare URL.
    Returns the Race instance (created or updated), or None on hard failure.
    """
    from cycling.models import Race

    soup = None
    # Stage races have a /gc endpoint; 1-day races use /result
    for suffix in ("gc", "result", ""):
        url = f"{PCS_BASE_URL}/race/{slug}/{year}/{suffix}".rstrip("/")
        soup = get_soup(url, live=live)
        if soup:
            break

    if not soup:
        logger.warning("sync_race: could not fetch %s/%d", slug, year)
        # Still upsert a minimal Race record so callers don't get None
        race, _ = Race.objects.get_or_create(
            slug=slug,
            year=year,
            defaults={"name": slug.replace("-", " ").title()},
        )
        return race

    race_data = _parse_race_detail_soup(soup, slug, year)
    if not race_data.get("name"):
        race_data["name"] = slug.replace("-", " ").title()

    race, _ = Race.objects.update_or_create(
        slug=slug,
        year=year,
        defaults=race_data,
    )

    # Parse GC / 1-day result table
    result_type = "stage" if race.is_stage_race else "gc"
    _parse_results_table(soup, race, stage=None, result_type=result_type)

    return race


def sync_stages(race, live: bool = False) -> list:
    """Fetch the stages list page for *race* and persist Stage objects.

    Returns list of Stage instances.
    """
    url = f"{PCS_BASE_URL}/race/{race.slug}/{race.year}/stages"
    soup = get_soup(url, live=live)
    if not soup:
        logger.warning("sync_stages: could not fetch stages for %s/%d", race.slug, race.year)
        return []
    stages = _parse_stages_soup(soup, race)
    logger.info("sync_stages: %d stages saved for %s/%d", len(stages), race.slug, race.year)
    return stages


def sync_stage_results(race, stage, live: bool = False) -> list:
    """Fetch and persist results for a specific stage.

    Returns list of RaceResult instances.
    """
    # Try /stage-N/result first, fall back to /stage-N
    for url_pattern in (
        f"{PCS_BASE_URL}/race/{race.slug}/{race.year}/stage-{stage.number}/result",
        f"{PCS_BASE_URL}/race/{race.slug}/{race.year}/stage-{stage.number}",
    ):
        soup = get_soup(url_pattern, live=live)
        if soup:
            break
    else:
        logger.warning(
            "sync_stage_results: could not fetch stage %d of %s/%d",
            stage.number, race.slug, race.year,
        )
        return []

    results = _parse_results_table(soup, race, stage=stage, result_type="stage")
    logger.info(
        "sync_stage_results: %d results saved for %s/%d stage %d",
        len(results), race.slug, race.year, stage.number,
    )
    return results


def sync_rankings(year: int) -> int:
    """Sync the top-500 PCS season individual rankings for *year*.

    PCS paginates at 100 per page using ?offset=0,100,200,…

    Returns total number of ranking entries saved.
    """
    total = 0
    for offset in range(0, 500, 100):
        url = (
            f"{PCS_BASE_URL}/rankings.php"
            f"?s=season-individual&offset={offset}&year={year}"
        )
        soup = get_soup(url)
        if not soup:
            logger.warning("sync_rankings: could not fetch offset=%d year=%d", offset, year)
            break
        n = _parse_rankings_page(soup, year)
        total += n
        if n == 0:
            break   # No more rows; stop early
    logger.info("sync_rankings: %d ranking entries saved for %d", total, year)
    return total


def sync_team(slug: str, year: int):
    """Fetch a team detail page and persist Team + rider roster data.

    Returns the Team instance, or None on failure.
    """
    from cycling.models import Team

    url = f"{PCS_BASE_URL}/team/{slug}-{year}"
    soup = get_soup(url)
    if not soup:
        logger.warning("sync_team: could not fetch %s-%d", slug, year)
        return None

    team_data = _parse_team_page_soup(soup, slug, year)
    if not team_data.get("name"):
        team_data["name"] = slug.replace("-", " ").title()

    team, _ = Team.objects.update_or_create(
        slug=slug,
        year=year,
        defaults=team_data,
    )

    _save_team_roster(team, soup)
    logger.info("sync_team: saved %s/%d", slug, year)
    return team


def find_ongoing_races() -> QuerySet:
    """Return a QuerySet of Race objects active today.

    Queries the DB first; if no races are found it triggers sync_races_year()
    for the current year and re-queries.
    """
    from cycling.models import Race

    today = date.today()
    year = today.year

    qs = Race.objects.filter(
        start_date__lte=today,
        end_date__gte=today,
        year=year,
    ).order_by("start_date")

    if qs.exists():
        return qs

    logger.info("find_ongoing_races: no ongoing races in DB for %s — syncing from PCS", today)
    try:
        sync_races_year(year)
    except Exception as exc:
        logger.warning("find_ongoing_races: sync_races_year failed: %s", exc)

    return Race.objects.filter(
        start_date__lte=today,
        end_date__gte=today,
        year=year,
    ).order_by("start_date")
