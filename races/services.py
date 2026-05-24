import logging
import re as _re
from datetime import date, datetime

from django.utils.text import slugify
from django.core.cache import cache

from core.services import pcs_get, PCS_BASE_URL

logger = logging.getLogger(__name__)

_ORDINAL_PREFIX = _re.compile(r'^\d+(st|nd|rd|th)\s*', _re.IGNORECASE)
_CLASS_SUFFIX   = _re.compile(r'\s*\([^)]*\)\s*$')
_EDITION_SUFFIX = _re.compile(r'\s*\[?\d+(st|nd|rd|th)\]?\s*$', _re.IGNORECASE)

# Circuits: 1=WorldTour, 26=ProSeries, 2=WorldChampionships
_RACE_CIRCUITS = [
    ('1',  'UCI World Tour'),
    ('26', 'UCI ProSeries'),
    ('2',  'UCI World Championships'),
]

# Grand Tours & Monuments by slug (fast lookup)
_GRAND_TOUR_SLUGS = {
    'tour-de-france', 'giro-d-italia', 'vuelta-a-espana',
    'tour-de-france-femmes-avec-zwift',
}
_MONUMENT_SLUGS = {
    'milano-sanremo', 'ronde-van-vlaanderen', 'paris-roubaix',
    'liege-bastogne-liege', 'il-lombardia',
}


def _clean_race_name(raw):
    name = raw.replace('\xa0', ' ').replace('»', '').replace('»', '').strip()
    name = _re.sub(r'^\d{4}\s*', '', name).strip()
    name = _ORDINAL_PREFIX.sub('', name)
    name = _CLASS_SUFFIX.sub('', name)
    name = _EDITION_SUFFIX.sub('', name)
    return name.strip(' -|')


# ─── Race list ────────────────────────────────────────────────

def fetch_races_by_year(year):
    """Fetch all races for a given year from PCS and save to DB."""
    from races.models import Race
    saved = 0
    for circuit_id, circuit_name in _RACE_CIRCUITS:
        url = (
            f"{PCS_BASE_URL}/races.php?year={year}"
            f"&circuit={circuit_id}&class=&filter=Filter"
        )
        soup = pcs_get(url, referer=f"{PCS_BASE_URL}/races.php")
        if soup:
            saved += _parse_and_save_races_list(soup, year, circuit_name)
        else:
            logger.warning("Could not fetch races circuit=%s year=%s", circuit_id, year)
    logger.info("fetch_races_by_year: %s races saved for %s", saved, year)
    return Race.objects.filter(year=year).order_by('start_date')


def find_races_today():
    """
    Look for races happening today.
    First checks the DB, then if nothing is found tries to auto-discover from
    PCS by fetching the WorldTour and ProSeries race lists for the current year.
    Returns a queryset of Race objects active today.
    """
    from races.models import Race
    today = date.today()
    year  = today.year

    qs = Race.objects.filter(
        start_date__lte=today,
        end_date__gte=today,
        year=year,
    ).order_by('start_date')

    if qs.exists():
        return qs

    # Nothing in DB — try to discover from PCS race list
    logger.info("No ongoing races in DB for today (%s), fetching from PCS…", today)
    try:
        fetch_races_by_year(year)
    except Exception as exc:
        logger.warning("Auto-discover races today failed: %s", exc)

    return Race.objects.filter(
        start_date__lte=today,
        end_date__gte=today,
        year=year,
    ).order_by('start_date')


# ─── Race detail ──────────────────────────────────────────────

def fetch_race_detail(race_slug, year, live=False):
    """Fetch race page and parse results + stages.

    Args:
        race_slug: PCS race slug.
        year: Race year.
        live: If True, bypass the page cache for a fully fresh fetch.
    """
    from races.models import Race

    soup = None
    # cache_timeout=90 for live fetches (90-second freshness window)
    ct = 90 if live else 3600

    for suffix in ('gc', 'result', ''):
        url = f"{PCS_BASE_URL}/race/{race_slug}/{year}/{suffix}".rstrip('/')
        soup = pcs_get(url, cache_timeout=ct, referer=f"{PCS_BASE_URL}/races.php", force=live)
        if soup:
            break

    race_data = _parse_race_page(soup, race_slug, year) if soup else {}

    if not race_data.get('name'):
        race_data['name'] = race_slug.replace('-', ' ').title()

    race, _ = Race.objects.update_or_create(
        slug=race_slug, year=year,
        defaults=race_data,
    )

    if soup:
        _parse_and_save_results(race, soup)

    # Also try to fetch/update the stages list (always useful for stage races)
    if race.is_stage_race or race.stages_count > 1:
        try:
            _fetch_and_save_stages(race, live=live)
        except Exception as exc:
            logger.debug("Could not refresh stages for %s: %s", race_slug, exc)

    return race


# ─── Live helpers ──────────────────────────────────────────────

def fetch_live_race_data(race):
    """
    Fetch the freshest available data for an ongoing race.
    Returns a dict with:
      - gc: list of GC result dicts
      - stage_results: list of current/latest stage result dicts
      - current_stage: Stage object or None
      - stages: list of all Stage objects
    """
    from races.models import Stage
    from riders.models import RaceResult

    today = date.today()

    # 1. Find the current (or most recent completed) stage
    current_stage = (
        Stage.objects.filter(race=race, date=today).first()
        or Stage.objects.filter(race=race, date__lte=today).order_by('-date').first()
    )

    # 2. Force-fresh fetch of the current stage page if it exists
    stage_results = []
    if current_stage:
        stage_results = _fetch_live_stage_results(race, current_stage)

    # 3. Force-fresh fetch of GC
    _fetch_live_gc(race)

    gc_qs = (
        RaceResult.objects.filter(race=race, result_type='gc', stage__isnull=True)
        .select_related('rider', 'team')
        .order_by('rank')[:20]
    )

    all_stages = list(
        Stage.objects.filter(race=race).order_by('number').select_related('winner', 'winner_team')
    )

    return {
        'gc': list(gc_qs),
        'stage_results': stage_results,
        'current_stage': current_stage,
        'stages': all_stages,
    }


def _fetch_live_gc(race):
    """Force-fresh fetch and save of GC standings."""
    for suffix in ('gc', 'result', ''):
        url = f"{PCS_BASE_URL}/race/{race.slug}/{race.year}/{suffix}".rstrip('/')
        soup = pcs_get(url, cache_timeout=90, force=True)
        if soup:
            _parse_and_save_results(race, soup)
            return soup
    return None


def _fetch_live_stage_results(race, stage):
    """Fetch stage results page for a specific stage (force-fresh). Returns list of dicts."""
    from races.models import Stage
    from riders.models import RaceResult, Rider
    from teams.models import Team

    url = f"{PCS_BASE_URL}/race/{race.slug}/{race.year}/stage-{stage.number}/result"
    soup = pcs_get(url, cache_timeout=90, force=True)
    if not soup:
        # Try alternative URL patterns
        url2 = f"{PCS_BASE_URL}/race/{race.slug}/{race.year}/stage-{stage.number}"
        soup = pcs_get(url2, cache_timeout=90, force=True)
    if not soup:
        return []

    results = []
    try:
        table = soup.find('table', class_='results')
        if not table:
            return []
        for row in table.select('tbody tr')[:30]:
            cols = row.find_all('td')
            if len(cols) < 4:
                continue
            rank_text = cols[0].get_text(strip=True)
            rank = int(rank_text) if rank_text.isdigit() else None
            if not rank:
                continue

            rider_col = row.find('td', class_='ridername') or row.find('a', href=lambda h: h and 'rider/' in h)
            if hasattr(rider_col, 'parent') and not hasattr(rider_col, 'find_all'):
                rider_col = rider_col.parent
            if not rider_col:
                continue

            rider_link = (rider_col.find('a', href=lambda h: h and 'rider/' in h)
                          if hasattr(rider_col, 'find') else rider_col)
            if not rider_link:
                continue

            rider_href  = rider_link.get('href', '').lstrip('/')
            rider_slug  = rider_href[6:] if rider_href.startswith('rider/') else rider_href
            rider_name  = rider_link.get_text(strip=True)

            nat = ''
            if hasattr(rider_col, 'find'):
                flag = rider_col.find('span', class_='flag')
                if flag:
                    cls = flag.get('class', [])
                    nat = cls[1].upper() if len(cls) > 1 else ''

            time_val = ''
            for td in cols:
                cl = ' '.join(td.get('class', []))
                if 'time' in cl or ('fs11' in cl):
                    t = td.get_text(strip=True)
                    if t and t not in ('', '-'):
                        time_val = t
                        break

            team_obj = None
            team_link = row.find('a', href=lambda h: h and 'team/' in h)
            if team_link:
                th = team_link.get('href', '').lstrip('/')
                if th.startswith('team/'):
                    ts = th[5:][:-5].rstrip('-')
                    team_obj = (Team.objects.filter(slug=ts, year=race.year).first()
                                or Team.objects.filter(slug=ts).order_by('-year').first())

            rider, _ = Rider.objects.get_or_create(
                slug=rider_slug,
                defaults={'name': rider_name, 'nationality': nat},
            )
            if not rider.nationality and nat:
                rider.nationality = nat
                rider.save(update_fields=['nationality'])

            RaceResult.objects.update_or_create(
                rider=rider, race=race, stage=stage, result_type='stage', year=race.year,
                defaults={'rank': rank, 'team': team_obj, 'time_gap': time_val[:20]},
            )

            results.append({
                'rank': rank,
                'rider_name': rider_name,
                'rider_url': rider.get_absolute_url(),
                'rider_flag': rider.flag_code,
                'team': team_obj.name if team_obj else '',
                'time_gap': time_val,
            })

            # Update stage winner if rank == 1
            if rank == 1:
                from races.models import Stage as StageModel
                StageModel.objects.filter(pk=stage.pk).update(winner=rider, winner_team=team_obj)

    except Exception as exc:
        logger.error("Error fetching live stage results for %s stage %s: %s",
                     race, stage.number, exc)

    return results


# ─── Stage fetching ────────────────────────────────────────────

def fetch_stages_for_race(race):
    """Fetch stages list from PCS and save to DB. Returns list of Stage objects."""
    return _fetch_and_save_stages(race, live=False)


def _fetch_and_save_stages(race, live=False):
    from races.models import Stage
    url = f"{PCS_BASE_URL}/race/{race.slug}/{race.year}/stages"
    soup = pcs_get(url, cache_timeout=90 if live else 3600, force=live)
    if not soup:
        return []

    stages = []
    try:
        for row in soup.select('table.results tbody tr, table.basic tbody tr'):
            cols = row.find_all('td')
            if len(cols) < 3:
                continue

            stage_link = row.find('a', href=lambda h: h and '/stage-' in h)
            if not stage_link:
                continue

            href = stage_link.get('href', '')
            parts = href.split('/stage-')
            if len(parts) < 2:
                continue
            stage_part = parts[1].split('/')[0]
            if not stage_part.isdigit():
                continue
            stage_num = int(stage_part)

            # Date
            date_obj = None
            date_text = cols[0].get_text(strip=True) if cols else ''
            if date_text and '.' in date_text:
                try:
                    dp = date_text.split('.')
                    date_obj = datetime(race.year, int(dp[1]), int(dp[0])).date()
                except Exception:
                    pass

            dep   = cols[1].get_text(strip=True) if len(cols) > 1 else ''
            arr   = cols[2].get_text(strip=True) if len(cols) > 2 else ''
            dist  = None
            if len(cols) > 3:
                m = _re.search(r'(\d+(?:\.\d+)?)', cols[3].get_text(strip=True))
                if m:
                    dist = float(m.group(1))

            stage_type = 'flat'
            if len(cols) > 4:
                type_text = cols[4].get_text(strip=True).lower()
                if 'mountain' in type_text or 'haut' in type_text:
                    stage_type = 'mountain'
                elif 'hilly' in type_text or 'vallonné' in type_text:
                    stage_type = 'hilly'
                elif 'tt' in type_text or 'time trial' in type_text or 'contre' in type_text:
                    stage_type = 'tt'
                elif 'cobble' in type_text or 'pavé' in type_text:
                    stage_type = 'cobbles'
                elif 'prologue' in type_text:
                    stage_type = 'prologue'

            # Winner from the row
            winner_obj  = None
            winner_team = None
            winner_link = row.find('a', href=lambda h: h and 'rider/' in h)
            if winner_link:
                rider_slug = winner_link.get('href', '').lstrip('/')[6:]
                from riders.models import Rider
                winner_obj = Rider.objects.filter(slug=rider_slug).first()

            stage, _ = Stage.objects.update_or_create(
                race=race, number=stage_num,
                defaults={
                    'date': date_obj,
                    'departure': dep[:100],
                    'arrival': arr[:100],
                    'distance': dist,
                    'stage_type': stage_type,
                    'winner': winner_obj,
                },
            )
            stages.append(stage)

    except Exception as exc:
        logger.error("Error parsing stages for %s: %s", race, exc)

    return stages


# ─── Race detail page parsing ──────────────────────────────────

def _parse_race_page(soup, race_slug, year):
    data = {}
    try:
        h1 = soup.find('h1')
        if h1:
            raw = h1.get_text(strip=True).replace(str(year), '')
            name_candidate = _clean_race_name(raw)
            data['name'] = name_candidate or race_slug.replace('-', ' ').title()
        else:
            data['name'] = race_slug.replace('-', ' ').title()

        data['year'] = year
        data['pcs_url'] = f"{PCS_BASE_URL}/race/{race_slug}/{year}"

        # Grand Tour / Monument by slug
        data['is_grand_tour'] = race_slug in _GRAND_TOUR_SLUGS
        data['is_monument']   = race_slug in _MONUMENT_SLUGS

        for li in soup.find_all('li'):
            t = li.find('div', class_='title')
            v = li.find('div', class_='value')
            if not t or not v:
                continue
            key = t.get_text(strip=True).lower().rstrip(':').strip()
            val = v.get_text(strip=True)
            if not val:
                continue
            if key == 'classification':
                data['classification'] = val[:10]
                data['is_stage_race'] = val.startswith('2.')
            elif key == 'distance':
                m = _re.search(r'[\d.,]+', val)
                if m:
                    try:
                        data['distance'] = float(m.group().replace(',', '.'))
                    except ValueError:
                        pass
            elif key in ('country', 'nation', 'country of origin'):
                data['country_name'] = val
            elif key == 'departure':
                data['departure_city'] = val[:100]
            elif key == 'arrival':
                data['arrival_city'] = val[:100]
            elif key in ('startdate', 'start date', 'date'):
                try:
                    dp = val.split('.')
                    if len(dp) >= 3:
                        data['start_date'] = datetime(int(dp[2]), int(dp[1]), int(dp[0])).date()
                except Exception:
                    pass
            elif key in ('enddate', 'end date'):
                try:
                    dp = val.split('.')
                    if len(dp) >= 3:
                        data['end_date'] = datetime(int(dp[2]), int(dp[1]), int(dp[0])).date()
                except Exception:
                    pass
            elif key in ('stages', 'etapes', 'étapes'):
                try:
                    data['stages_count'] = int(_re.search(r'\d+', val).group())
                except Exception:
                    pass

        profile_img = soup.find('img', src=lambda s: s and 'profile' in s.lower())
        if profile_img:
            src = profile_img['src']
            data['profile_url'] = src if src.startswith('http') else f"{PCS_BASE_URL}/{src.lstrip('/')}"

    except Exception as exc:
        logger.error("Error parsing race page %s %s: %s", race_slug, year, exc)
    return data


def _parse_and_save_races_list(soup, year, circuit_name=''):
    from races.models import Race
    saved = 0
    try:
        table = soup.find('table', class_='basic')
        if not table:
            return 0
        for row in table.select('tbody tr'):
            cols = row.find_all('td')
            if len(cols) < 3:
                continue
            name_link = None
            for col in cols:
                a = col.find('a', href=lambda h: h and 'race/' in h)
                if a:
                    name_link = a
                    break
            if not name_link:
                continue
            name = _clean_race_name(name_link.get_text(strip=True))
            href = name_link.get('href', '').lstrip('/')
            parts = href.split('/')
            slug = parts[1] if len(parts) > 1 else slugify(name)

            country = ''
            name_col = next((c for c in cols if c.find('a', href=lambda h: h and 'race/' in h)), None)
            if name_col:
                flag = name_col.find('span', class_='flag')
                if flag:
                    cls = flag.get('class', [])
                    country = cls[1].upper() if len(cls) > 1 else ''

            classification = cols[-1].get_text(strip=True)[:10] if cols else ''
            date_range = cols[0].get_text(strip=True) if cols else ''
            start_date = end_date = None

            try:
                start_raw = cols[1].get_text(strip=True) if len(cols) > 1 else ''
                if start_raw and '.' in start_raw:
                    day, mon = start_raw.split('.')[:2]
                    start_date = datetime(year, int(mon), int(day)).date()
            except Exception:
                pass

            try:
                if ' - ' in date_range:
                    end_raw = date_range.split(' - ')[-1].strip()
                elif date_range and '.' in date_range:
                    end_raw = date_range.split(' ')[0].strip()
                else:
                    end_raw = ''
                if end_raw and '.' in end_raw:
                    parts_e = end_raw.split('.')
                    end_date = datetime(year, int(parts_e[1]), int(parts_e[0])).date()
            except Exception:
                pass

            if not end_date:
                end_date = start_date

            _, _ = Race.objects.update_or_create(
                slug=slug, year=year,
                defaults={
                    'name': name,
                    'classification': classification,
                    'circuit': circuit_name[:50],
                    'country': country,
                    'start_date': start_date,
                    'end_date': end_date,
                    'is_grand_tour': slug in _GRAND_TOUR_SLUGS,
                    'is_monument': slug in _MONUMENT_SLUGS,
                    'is_stage_race': classification.startswith('2.'),
                },
            )
            saved += 1
    except Exception as exc:
        logger.error("Error parsing races list: %s", exc)
    return saved


def _parse_and_save_results(race, soup):
    """Parse GC/result table and save RaceResult objects."""
    from riders.models import Rider, RaceResult
    from teams.models import Team
    try:
        table = soup.find('table', class_='results')
        if not table:
            return

        winner = None
        for row in table.select('tbody tr'):
            cols = row.find_all('td')
            if len(cols) < 5:
                continue
            rank_text = cols[0].get_text(strip=True)
            rank = int(rank_text) if rank_text.isdigit() else None

            rider_col = row.find('td', class_='ridername')
            if not rider_col:
                a = row.find('a', href=lambda h: h and 'rider/' in h)
                rider_col = a.parent if a else None
            if not rider_col:
                continue

            rider_link = rider_col.find('a', href=lambda h: h and 'rider/' in h)
            if not rider_link:
                continue
            rider_href = rider_link.get('href', '').lstrip('/')
            rider_slug = rider_href[6:] if rider_href.startswith('rider/') else rider_href
            rider_name = rider_link.get_text(strip=True)

            rider_nat = ''
            flag_span = rider_col.find('span', class_='flag')
            if flag_span:
                cls = flag_span.get('class', [])
                rider_nat = cls[1].upper() if len(cls) > 1 else ''

            time_gap = ''
            for td in cols:
                cl = ' '.join(td.get('class', []))
                if 'fs11' in cl and 'clr666' in cl:
                    val = td.get_text(strip=True)
                    if '+' in val or val == '-':
                        time_gap = val
                        break

            team_obj = None
            team_link = row.find('a', href=lambda h: h and 'team/' in h)
            if team_link:
                th = team_link.get('href', '').lstrip('/')
                if th.startswith('team/'):
                    ts = th[5:][:-5].rstrip('-')
                    team_obj = (Team.objects.filter(slug=ts, year=race.year).first()
                                or Team.objects.filter(slug=ts).order_by('-year').first())

            rider, created = Rider.objects.get_or_create(
                slug=rider_slug,
                defaults={'name': rider_name, 'nationality': rider_nat},
            )
            if not created and rider_nat and not rider.nationality:
                rider.nationality = rider_nat
                rider.save(update_fields=['nationality'])

            RaceResult.objects.update_or_create(
                rider=rider, race=race, year=race.year, stage=None, result_type='gc',
                defaults={'rank': rank, 'team': team_obj, 'time_gap': time_gap[:20]},
            )

            if rank == 1:
                winner = rider
                winner_team = team_obj

        # Update race winner
        if winner:
            race.__class__.objects.filter(pk=race.pk).update(
                winner=winner,
                winner_team=winner_team if 'winner_team' in dir() else None,
            )

    except Exception as exc:
        logger.error("Error parsing results for %s: %s", race, exc)
