import logging
from django.utils.text import slugify
from django.core.cache import cache
from core.services import pcs_get, get_pcs_scraper, PCS_BASE_URL

logger = logging.getLogger(__name__)


def fetch_races_by_year(year):
    """Fetch all races for a given year using pcs_scraper."""
    from races.models import Race
    pcs = get_pcs_scraper()
    if pcs:
        try:
            race_options = pcs.race_options_by_year(year)
            if race_options is not None and not race_options.empty:
                for _, row in race_options.iterrows():
                    name = str(row.get('race', '')).strip()
                    if not name:
                        continue
                    race_slug = slugify(name)
                    classification = str(row.get('classification', '')).strip()
                    circuit = str(row.get('circuit', '')).strip()
                    Race.objects.update_or_create(
                        slug=race_slug, year=year,
                        defaults={
                            'name': name,
                            'classification': classification[:10] if classification else '',
                            'circuit': circuit[:50] if circuit else '',
                        }
                    )
                return Race.objects.filter(year=year)
        except Exception as exc:
            logger.warning("pcs_scraper race_options_by_year failed for %s: %s", year, exc)

    soup = pcs_get(f"{PCS_BASE_URL}/races.php?year={year}&circuit=1&class=2.UWT")
    if soup:
        _parse_and_save_races_list(soup, year)

    return Race.objects.filter(year=year).order_by('start_date')


def fetch_race_detail(race_slug, year):
    """Fetch detailed race data and save to database."""
    from races.models import Race
    pcs = get_pcs_scraper()
    gc_results = None
    if pcs:
        try:
            race_obj = pcs.Race(name=race_slug, year=year)
            gc_results = race_obj.get_results()
        except Exception as exc:
            logger.warning("pcs_scraper Race failed for %s %s: %s", race_slug, year, exc)

    soup = pcs_get(f"{PCS_BASE_URL}/race/{race_slug}/{year}/gc")
    if not soup:
        soup = pcs_get(f"{PCS_BASE_URL}/race/{race_slug}/{year}")

    race_data = _parse_race_page(soup, race_slug, year) if soup else {}

    race, created = Race.objects.update_or_create(
        slug=race_slug, year=year,
        defaults=race_data if race_data else {'name': race_slug.replace('-', ' ').title(), 'year': year}
    )

    if gc_results is not None and not gc_results.empty:
        _save_gc_results(race, gc_results)
    elif soup:
        _parse_and_save_results(race, soup)

    return race


def _parse_race_page(soup, race_slug, year):
    """Parse race detail page."""
    data = {}
    try:
        h1 = soup.find('h1')
        if h1:
            data['name'] = h1.get_text(strip=True).split(str(year))[0].strip()
        else:
            data['name'] = race_slug.replace('-', ' ').title()

        data['year'] = year
        data['pcs_url'] = f"{PCS_BASE_URL}/race/{race_slug}/{year}"

        info_div = soup.find('div', class_='infolist')
        if info_div:
            for li in info_div.find_all('li'):
                spans = li.find_all('span')
                if len(spans) >= 2:
                    key = spans[0].get_text(strip=True).lower()
                    val = spans[1].get_text(strip=True)
                    if 'date' in key:
                        pass
                    elif 'country' in key or 'nation' in key:
                        data['country_name'] = val
                    elif 'classification' in key or 'cat' in key:
                        data['classification'] = val[:10]
    except Exception as exc:
        logger.error("Error parsing race page %s %s: %s", race_slug, year, exc)
    return data


def _parse_and_save_races_list(soup, year):
    """Parse race list page and save to database."""
    from races.models import Race
    try:
        for row in soup.select('table tbody tr'):
            cols = row.find_all('td')
            if len(cols) < 3:
                continue
            name_link = cols[1].find('a') if len(cols) > 1 else None
            if not name_link:
                continue
            name = name_link.get_text(strip=True)
            href = name_link.get('href', '')
            slug = href.split('/race/')[-1].split('/')[0] if '/race/' in href else slugify(name)
            Race.objects.update_or_create(
                slug=slug, year=year,
                defaults={'name': name, 'year': year}
            )
    except Exception as exc:
        logger.error("Error parsing races list: %s", exc)


def _parse_and_save_results(race, soup):
    """Parse GC results from race page."""
    from riders.models import Rider, RaceResult
    try:
        table = soup.find('table', class_='results')
        if not table:
            return
        for row in table.select('tbody tr'):
            cols = row.find_all('td')
            if len(cols) < 3:
                continue
            rank_text = cols[0].get_text(strip=True)
            rider_link = row.find('a', href=lambda h: h and '/rider/' in h)
            if not rider_link:
                continue
            rider_name = rider_link.get_text(strip=True)
            rider_slug = rider_link['href'].split('/rider/')[-1].strip('/')
            rank = int(rank_text) if rank_text.isdigit() else None
            rider, _ = Rider.objects.get_or_create(
                slug=rider_slug,
                defaults={'name': rider_name}
            )
            RaceResult.objects.update_or_create(
                rider=rider, race=race, year=race.year, stage=None, result_type='gc',
                defaults={'rank': rank}
            )
    except Exception as exc:
        logger.error("Error parsing results for %s: %s", race, exc)


def _save_gc_results(race, df):
    """Save GC results DataFrame to database."""
    from riders.models import Rider, RaceResult
    if df is None or df.empty:
        return
    for _, row in df.iterrows():
        try:
            rider_name = str(row.get('rider', '')).strip()
            if not rider_name:
                continue
            rider_slug = slugify(rider_name)
            rank_val = row.get('result') or row.get('rank')
            rank = int(rank_val) if str(rank_val).isdigit() else None
            rider, _ = Rider.objects.get_or_create(
                slug=rider_slug,
                defaults={'name': rider_name}
            )
            RaceResult.objects.update_or_create(
                rider=rider, race=race, year=race.year, stage=None, result_type='gc',
                defaults={'rank': rank, 'points': float(row.get('points', 0) or 0)}
            )
        except Exception as exc:
            logger.debug("Skipping GC result row: %s", exc)


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
