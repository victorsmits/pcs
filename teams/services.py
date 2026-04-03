import logging
from django.utils.text import slugify
from django.core.cache import cache
from core.services import pcs_get, PCS_BASE_URL

logger = logging.getLogger(__name__)


def fetch_teams_by_year(year, gender='M'):
    """Fetch all teams for a given year using cloudscraper HTML parsing."""
    from teams.models import Team
    s = 'women' if gender in ('F', 'Female', 'Women') else 'men'
    url = f"{PCS_BASE_URL}/teams.php?year={year}&filter=Filter&s={s}"
    soup = pcs_get(url, referer=f"{PCS_BASE_URL}/teams.php")
    saved = 0
    if soup:
        saved = _parse_and_save_teams(soup, year)
        logger.info("fetch_teams_by_year: %s teams saved for %s", saved, year)
    else:
        logger.warning("Could not fetch teams for year %s", year)
    return Team.objects.filter(year=year).order_by('name')


def fetch_team_detail(team_slug, year):
    """Fetch team page, parse metadata and rider roster."""
    from teams.models import Team

    soup = pcs_get(f"{PCS_BASE_URL}/team/{team_slug}-{year}")
    team_data = _parse_team_page(soup, team_slug, year) if soup else {}

    team, _ = Team.objects.update_or_create(
        slug=team_slug, year=year,
        defaults=team_data if team_data else {'name': team_slug.replace('-', ' ').title(), 'year': year}
    )

    if soup:
        _parse_and_save_team_riders(team, soup)

    return team


_COUNTRY_SLUG_TO_IOC = {
    'belgium': 'BEL', 'france': 'FRA', 'italy': 'ITA', 'spain': 'ESP',
    'netherlands': 'NLD', 'great-britain': 'GBR', 'germany': 'DEU',
    'australia': 'AUS', 'united-states': 'USA', 'switzerland': 'CHE',
    'denmark': 'DNK', 'norway': 'NOR', 'sweden': 'SWE', 'colombia': 'COL',
    'slovenia': 'SVN', 'poland': 'POL', 'portugal': 'PRT', 'kazakhstan': 'KAZ',
    'lithuania': 'LTU', 'latvia': 'LAT', 'estonia': 'EST', 'slovakia': 'SVK',
    'czech-republic': 'CZE', 'austria': 'AUT', 'luxembourg': 'LUX',
    'south-africa': 'RSA', 'new-zealand': 'NZL', 'canada': 'CAN',
    'argentina': 'ARG', 'ecuador': 'ECU', 'eritrea': 'ERI', 'rwanda': 'RWA',
    'ukraine': 'UKR', 'russia': 'RUS', 'japan': 'JPN', 'china': 'CHN',
    'israel': 'ISR', 'bahrain': 'BHR', 'uae': 'UAE',
}


def _country_slug_to_ioc(slug):
    return _COUNTRY_SLUG_TO_IOC.get(slug.lower(), slug.upper()[:3])


def _parse_team_page(soup, team_slug, year):
    """Parse team detail page."""
    data = {}
    try:
        h1 = soup.find('h1')
        if h1:
            name_text = h1.get_text(strip=True)
            data['name'] = name_text.replace(str(year), '').strip()
        else:
            data['name'] = team_slug.replace('-', ' ').title()
        data['year'] = year
        data['pcs_url'] = f"{PCS_BASE_URL}/team/{team_slug}-{year}"

        img = soup.find('img', class_='teamlogo')
        if img and img.get('src'):
            src = img['src']
            data['logo_url'] = src if src.startswith('http') else PCS_BASE_URL + src

        for li in soup.select('ul.infolist li'):
            title_div = li.find('div', class_='title')
            value_div = li.find('div', class_='value')
            if not title_div or not value_div:
                continue
            key = title_div.get_text(strip=True).lower().rstrip(':').strip()
            val = value_div.get_text(strip=True)
            link = value_div.find('a', href=True)
            if 'status' in key or 'team status' in key:
                code = val.strip()
                _status_map = {'WT': 'WorldTeam', 'PT': 'ProTeam', 'CT': 'Continental'}
                data['status'] = _status_map.get(code, code)
            elif 'abbreviation' in key:
                data['abbreviation'] = val[:10]
            elif 'country' in key or 'license' in key or 'nation' in key:
                data['country_name'] = val
                if link:
                    nat_href = link.get('href', '')
                    country_slug = nat_href.split('/')[-1]
                    data['nationality'] = _country_slug_to_ioc(country_slug)
            elif 'bike' in key:
                data['bike_brand'] = val[:100]
            elif 'clothing' in key or 'kit' in key:
                data['clothing_brand'] = val[:100]
            elif 'manager' in key or 'directeur' in key:
                data['manager'] = val[:200]
            elif 'website' in key or 'web' in key:
                if link:
                    data['website'] = link.get('href', '')[:200]
    except Exception as exc:
        logger.error("Error parsing team page %s %s: %s", team_slug, year, exc)
    return data


_TEAM_STATUS_BY_GROUP = {0: 'WorldTeam', 2: 'ProTeam'}


def _parse_and_save_teams(soup, year):
    """Parse teams.php page (ul.list structure) and save. Returns count.

    PCS page has 4 ul.list elements:
      [0] WorldTeam names  [1] WorldTeam jerseys (skip)
      [2] ProTeam names    [3] ProTeam jerseys (skip)
    href format: team/slug-YEAR  (no leading slash)
    """
    from teams.models import Team
    saved = 0
    try:
        lists = soup.select('ul.list')
        # pairs: (ul_index, status)
        pairs = [(0, 'WorldTeam'), (2, 'ProTeam')]
        for ul_idx, status in pairs:
            if ul_idx >= len(lists):
                continue
            for li in lists[ul_idx].find_all('li'):
                link = li.find('a', href=True)
                if not link:
                    continue
                name = link.get_text(strip=True).strip()
                if not name:
                    continue
                href = link.get('href', '').lstrip('/')
                # href: team/ineos-grenadiers-2026  → slug = ineos-grenadiers
                if href.startswith('team/'):
                    raw_slug_year = href[5:]          # e.g. ineos-grenadiers-2026
                    slug = raw_slug_year[:-5].rstrip('-')  # remove -YEAR (5 chars)
                else:
                    slug = slugify(name)
                if not slug:
                    slug = slugify(name)
                Team.objects.update_or_create(
                    slug=slug, year=year,
                    defaults={'name': name, 'year': year, 'status': status}
                )
                saved += 1
    except Exception as exc:
        logger.error("Error parsing teams list: %s", exc)
    return saved


def _save_team_riders(team, df):
    """Save team riders DataFrame to TeamRoster."""
    from riders.models import Rider
    from teams.models import TeamRoster
    if df is None or df.empty:
        return
    for _, row in df.iterrows():
        try:
            rider_name = str(row.get('rider', '')).strip()
            if not rider_name:
                continue
            rider_slug = slugify(rider_name)
            nationality = str(row.get('nationality', '')).strip()[:3]
            rider, _ = Rider.objects.get_or_create(
                slug=rider_slug,
                defaults={'name': rider_name, 'nationality': nationality}
            )
            TeamRoster.objects.get_or_create(team=team, rider=rider)
        except Exception as exc:
            logger.debug("Skipping rider row: %s", exc)


def _parse_and_save_team_riders(team, soup):
    """Parse team page and save riders to TeamRoster."""
    from riders.models import Rider
    from teams.models import TeamRoster
    try:
        seen = set()
        for a in soup.find_all('a', href=True):
            href = a.get('href', '').lstrip('/')
            if not href.startswith('rider/'):
                continue
            rider_slug = href[6:].strip('/')
            rider_name = a.get_text(strip=True)
            if not rider_slug or not rider_name or rider_slug in seen:
                continue
            seen.add(rider_slug)
            flag = a.find_previous_sibling('span', class_='flag') or \
                   a.find_next_sibling('span', class_='flag')
            nat = ''
            if flag:
                cls = [c for c in flag.get('class', []) if c != 'flag']
                nat = cls[0].upper() if cls else ''
            rider, _ = Rider.objects.get_or_create(
                slug=rider_slug,
                defaults={'name': rider_name, 'nationality': nat}
            )
            if nat and not rider.nationality:
                rider.nationality = nat
                rider.save(update_fields=['nationality'])
            TeamRoster.objects.get_or_create(team=team, rider=rider)
    except Exception as exc:
        logger.error("Error parsing team riders: %s", exc)
