import logging
import re as _re
from django.utils.text import slugify
from django.core.cache import cache
from core.services import pcs_get, PCS_BASE_URL

logger = logging.getLogger(__name__)


_ORDINAL_PREFIX = _re.compile(r'^\d+(st|nd|rd|th)\s*', _re.IGNORECASE)
_CLASS_SUFFIX   = _re.compile(r'\s*\([^)]*\)\s*$')
_EDITION_SUFFIX = _re.compile(r'\s*\[?\d+(st|nd|rd|th)\]?\s*$', _re.IGNORECASE)


def _clean_race_name(raw):
    """Remove year prefix (2025 » ...), ordinal prefix (72nd), classification suffix (2.Pro)."""
    name = raw.replace('\xa0', ' ').replace('\u00bb', '').replace('»', '').strip()
    name = _re.sub(r'^\d{4}\s*', '', name).strip()
    name = _ORDINAL_PREFIX.sub('', name)
    name = _CLASS_SUFFIX.sub('', name)
    name = _EDITION_SUFFIX.sub('', name)
    return name.strip(' -|')


# Circuits: 1=WorldTour, 26=ProSeries, 2=WorldChampionships, ''=all
_RACE_CIRCUITS = [
    ('1',  'UCI World Tour'),
    ('26', 'UCI ProSeries'),
    ('2',  'UCI World Championships'),
]


def fetch_races_by_year(year):
    """Fetch all races for a given year using cloudscraper HTML parsing."""
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


def fetch_race_detail(race_slug, year):
    """Fetch race page and parse results. Tries /gc first (stage races), then /result (1-day)."""
    from races.models import Race

    soup = None
    for suffix in ('gc', 'result', ''):
        url = f"{PCS_BASE_URL}/race/{race_slug}/{year}/{suffix}".rstrip('/')
        soup = pcs_get(url, referer=f"{PCS_BASE_URL}/races.php")
        if soup:
            break

    race_data = _parse_race_page(soup, race_slug, year) if soup else {}

    if not race_data.get('name'):
        race_data['name'] = race_slug.replace('-', ' ').title()
    existing = Race.objects.filter(slug=race_slug, year=year).values_list('name', flat=True).first()
    if existing and not race_data.get('name'):
        race_data.pop('name', None)

    race, _ = Race.objects.update_or_create(
        slug=race_slug, year=year,
        defaults=race_data
    )

    if soup:
        _parse_and_save_results(race, soup)

    return race


def _parse_race_page(soup, race_slug, year):
    """Parse race detail page."""
    data = {}
    try:
        h1 = soup.find('h1')
        if h1:
            raw = h1.get_text(strip=True)
            raw = raw.replace(str(year), '')
            name_candidate = _clean_race_name(raw)
            data['name'] = name_candidate if name_candidate else race_slug.replace('-', ' ').title()
        else:
            data['name'] = race_slug.replace('-', ' ').title()

        data['year'] = year
        data['pcs_url'] = f"{PCS_BASE_URL}/race/{race_slug}/{year}"

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

        profile_img = soup.find('img', src=lambda s: s and 'profile' in s.lower())
        if profile_img:
            src = profile_img['src']
            data['profile_url'] = src if src.startswith('http') else f"{PCS_BASE_URL}/{src.lstrip('/')}"
    except Exception as exc:
        logger.error("Error parsing race page %s %s: %s", race_slug, year, exc)
    return data


def _parse_and_save_races_list(soup, year, circuit_name=''):
    """Parse race list page (races.php) and save to database. Returns count."""
    from races.models import Race
    import re
    from datetime import datetime
    saved = 0
    try:
        table = soup.find('table', class_='basic')
        if not table:
            return 0
        for row in table.select('tbody tr'):
            cols = row.find_all('td')
            if len(cols) < 3:
                continue
            # PCS columns: date | ? | name+link | country | classification
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
            # href format: race/slug/year or race/slug/year/gc
            parts = href.split('/')
            # parts[0]='race', parts[1]=slug, parts[2]=year
            slug = parts[1] if len(parts) > 1 else slugify(name)
            # country from flag span inside the name column
            country = ''
            name_col = next((c for c in cols if c.find('a', href=lambda h: h and 'race/' in h)), None)
            if name_col:
                flag = name_col.find('span', class_='flag')
                if flag:
                    cls = flag.get('class', [])
                    country = cls[1].upper() if len(cls) > 1 else ''
            # classification is usually in last col
            classification = cols[-1].get_text(strip=True)[:10] if cols else ''
            # col0 = date range 'DD.MM - DD.MM', col1 = start date 'DD.MM'
            date_range = cols[0].get_text(strip=True) if cols else ''
            start_date = end_date = None
            try:
                # parse start from col1 (just DD.MM)
                start_raw = cols[1].get_text(strip=True) if len(cols) > 1 else ''
                if start_raw and '.' in start_raw:
                    day, mon = start_raw.split('.')[:2]
                    start_date = datetime(year, int(mon), int(day)).date()
            except Exception:
                pass
            try:
                # parse end from col0 range, after ' - '
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
            # determine flags
            is_gt = name in ('Tour de France', 'Giro d\'Italia', 'Vuelta a Espana',
                             'Tour de France Femmes avec Zwift')
            is_monument = name in ('Milano-Sanremo', 'Ronde van Vlaanderen',
                                   'Paris-Roubaix', 'Liège-Bastogne-Liège',
                                   'Il Lombardia')
            _, created = Race.objects.update_or_create(
                slug=slug, year=year,
                defaults={
                    'name': name,
                    'classification': classification,
                    'circuit': circuit_name[:50],
                    'country': country,
                    'start_date': start_date,
                    'end_date': end_date,
                    'is_grand_tour': is_gt,
                    'is_monument': is_monument,
                    'is_stage_race': classification.startswith('2.'),
                }
            )
            saved += 1
    except Exception as exc:
        logger.error("Error parsing races list: %s", exc)
    return saved


def _parse_and_save_results(race, soup):
    """Parse GC/result table — works for both stage race /gc and 1-day /result pages.

    Locates columns by CSS class name instead of index because the two page
    types have different column layouts:
      /gc (stage):   col0=rank col1=prev col2=time_gap col3=bib ... col7=ridername col8=team
      /result (1day):col0=rank col1=bib  col2=h2h      col3=specialty ... col5=ridername col6=team
    href format: rider/slug  team/slug-YEAR  (no leading slash)
    """
    from riders.models import Rider, RaceResult
    from teams.models import Team
    try:
        table = soup.find('table', class_='results')
        if not table:
            return
        for row in table.select('tbody tr'):
            cols = row.find_all('td')
            if len(cols) < 5:
                continue
            rank_text = cols[0].get_text(strip=True)
            rank = int(rank_text) if rank_text.isdigit() else None

            # find rider column by class 'ridername'
            rider_col = row.find('td', class_='ridername')
            if not rider_col:
                rider_col = row.find('a', href=lambda h: h and 'rider/' in h)
                rider_col = rider_col.parent if rider_col else None
            if not rider_col:
                continue

            rider_link = rider_col.find('a', href=lambda h: h and 'rider/' in h)
            if not rider_link:
                continue
            rider_href = rider_link.get('href', '').lstrip('/')
            rider_slug = rider_href[6:] if rider_href.startswith('rider/') else rider_href
            rider_name = rider_link.get_text(strip=True)

            # nationality from flag span inside ridername cell
            rider_nat = ''
            flag_span = rider_col.find('span', class_='flag')
            if flag_span:
                cls = flag_span.get('class', [])
                rider_nat = cls[1].upper() if len(cls) > 1 else ''

            # time_gap: look for td with class 'fs11 clr666' (stage race only)
            time_gap = ''
            for td in cols:
                cl = ' '.join(td.get('class', []))
                if 'fs11' in cl and 'clr666' in cl:
                    val = td.get_text(strip=True)
                    if '+' in val or val == '-':
                        time_gap = val
                        break

            # team: find td immediately after ridername col
            team_obj = None
            team_link = row.find('a', href=lambda h: h and 'team/' in h)
            if team_link:
                th = team_link.get('href', '').lstrip('/')
                if th.startswith('team/'):
                    raw = th[5:]                     # e.g. uae-team-emirates-2024
                    ts = raw[:-5].rstrip('-')          # strip -YEAR suffix
                    team_obj = (Team.objects.filter(slug=ts, year=race.year).first() or
                                Team.objects.filter(slug=ts).order_by('-year').first())

            rider, created = Rider.objects.get_or_create(
                slug=rider_slug,
                defaults={'name': rider_name, 'nationality': rider_nat}
            )
            if not created and rider_nat and not rider.nationality:
                rider.nationality = rider_nat
                rider.save(update_fields=['nationality'])

            RaceResult.objects.update_or_create(
                rider=rider, race=race, year=race.year, stage=None, result_type='gc',
                defaults={'rank': rank, 'team': team_obj, 'time_gap': time_gap[:20]})

    except Exception as exc:
        logger.error("Error parsing results for %s: %s", race, exc)



def fetch_stages_for_race(race):
    """Fetch stages list for a stage race."""
    from races.models import Stage
    soup = pcs_get(f"{PCS_BASE_URL}/race/{race.slug}/{race.year}/stages")
    if not soup:
        return []
    stages = []
    try:
        for row in soup.select('table.results tbody tr, table tbody tr'):
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
            stage_num = int(parts[1].split('/')[0]) if parts[1].split('/')[0].isdigit() else None
            if not stage_num:
                continue
            date_text = cols[0].get_text(strip=True) if cols else ''
            dep = cols[1].get_text(strip=True) if len(cols) > 1 else ''
            arr = cols[2].get_text(strip=True) if len(cols) > 2 else ''
            dist_text = cols[3].get_text(strip=True) if len(cols) > 3 else ''
            dist = None
            import re
            m = re.search(r'(\d+(?:\.\d+)?)', dist_text)
            if m:
                dist = float(m.group(1))
            stage, _ = Stage.objects.update_or_create(
                race=race, number=stage_num,
                defaults={
                    'departure': dep[:100],
                    'arrival': arr[:100],
                    'distance': dist,
                }
            )
            stages.append(stage)
    except Exception as exc:
        logger.error("Error parsing stages for %s: %s", race, exc)
    return stages
