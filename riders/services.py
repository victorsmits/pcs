import logging
import pandas as pd
from django.utils.text import slugify
from django.core.cache import cache
from core.services import pcs_get, get_pcs_scraper, PCS_BASE_URL

logger = logging.getLogger(__name__)


def fetch_rider_from_pcs(rider_slug):
    """Fetch rider data from PCS and save/update in database."""
    from riders.models import Rider
    pcs = get_pcs_scraper()
    data = {}
    if pcs:
        try:
            rider_obj = pcs.Rider(name=rider_slug)
            race_history = rider_obj.get_race_history()
            if race_history is not None and not race_history.empty:
                data['race_history'] = race_history
        except Exception as exc:
            logger.warning("pcs_scraper failed for rider %s: %s", rider_slug, exc)

    soup = pcs_get(f"{PCS_BASE_URL}/rider/{rider_slug}")
    if not soup:
        return None

    rider_data = _parse_rider_page(soup, rider_slug)
    if not rider_data:
        return None

    rider, created = Rider.objects.update_or_create(
        slug=rider_slug,
        defaults=rider_data
    )
    if 'race_history' in data:
        _save_race_history(rider, data['race_history'])

    return rider


def _parse_rider_page(soup, rider_slug):
    """Parse rider profile page from BeautifulSoup."""
    data = {}
    try:
        h1 = soup.find('h1')
        if h1:
            data['name'] = h1.get_text(strip=True)
        else:
            data['name'] = rider_slug.replace('-', ' ').title()

        info_div = soup.find('div', class_='rdr-info-cont')
        if info_div:
            for li in info_div.find_all('li'):
                text = li.get_text(strip=True)
                if 'Date of birth:' in text or 'Born:' in text:
                    import re
                    from datetime import datetime
                    date_str = re.sub(r'(Date of birth:|Born:)\s*', '', text).strip()
                    try:
                        data['date_of_birth'] = datetime.strptime(date_str[:10], '%Y-%m-%d').date()
                    except Exception:
                        pass
                elif 'Weight:' in text:
                    import re
                    m = re.search(r'(\d+(?:\.\d+)?)\s*kg', text)
                    if m:
                        data['weight'] = float(m.group(1))
                elif 'Height:' in text:
                    import re
                    m = re.search(r'(\d+(?:\.\d+)?)\s*m', text)
                    if m:
                        data['height'] = float(m.group(1)) * 100

        img = soup.find('img', class_='rdr-photo')
        if img and img.get('src'):
            src = img['src']
            if src.startswith('http'):
                data['photo_url'] = src
            else:
                data['photo_url'] = PCS_BASE_URL + src

        data['pcs_url'] = f"{PCS_BASE_URL}/rider/{rider_slug}"
    except Exception as exc:
        logger.error("Error parsing rider page for %s: %s", rider_slug, exc)

    return data


def _save_race_history(rider, df):
    """Save race history DataFrame to RaceResult objects."""
    from races.models import Race
    from riders.models import RaceResult
    if df is None or df.empty:
        return
    for _, row in df.iterrows():
        try:
            race_name = str(row.get('race', '')).strip()
            year = int(row.get('year', 0)) if row.get('year') else None
            rank = row.get('result')
            if not race_name or not year:
                continue
            race_slug = slugify(race_name)
            race, _ = Race.objects.get_or_create(
                slug=race_slug, year=year,
                defaults={'name': race_name, 'year': year}
            )
            rank_val = None
            if rank and str(rank).isdigit():
                rank_val = int(rank)
            RaceResult.objects.update_or_create(
                rider=rider, race=race, year=year, stage=None, result_type='gc',
                defaults={'rank': rank_val, 'points': float(row.get('points', 0) or 0)}
            )
        except Exception as exc:
            logger.debug("Skipping race history row: %s", exc)


def search_riders_on_pcs(query):
    """Search for riders by name on PCS."""
    cache_key = f"rider_search_{slugify(query)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    soup = pcs_get(f"{PCS_BASE_URL}/search?q={query}&s=riders")
    results = []
    if soup:
        for a in soup.select('ul.list.riders li a'):
            href = a.get('href', '')
            name = a.get_text(strip=True)
            if '/rider/' in href:
                slug = href.split('/rider/')[-1].strip('/')
                results.append({'name': name, 'slug': slug, 'url': href})
    cache.set(cache_key, results, 1800)
    return results


def get_rider_career_stats(rider):
    """Compute career stats from stored results."""
    from riders.models import RaceResult
    results = RaceResult.objects.filter(rider=rider).select_related('race')
    wins = results.filter(rank=1).count()
    podiums = results.filter(rank__lte=3).count()
    top10 = results.filter(rank__lte=10).count()
    total = results.exclude(dnf=True).exclude(dns=True).count()
    return {
        'wins': wins,
        'podiums': podiums,
        'top10': top10,
        'total_races': total,
    }
