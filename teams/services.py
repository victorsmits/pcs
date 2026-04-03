import logging
from django.utils.text import slugify
from django.core.cache import cache
from core.services import pcs_get, get_pcs_scraper, PCS_BASE_URL

logger = logging.getLogger(__name__)


def fetch_teams_by_year(year, gender='M'):
    """Fetch all teams for a given year using pcs_scraper."""
    from teams.models import Team
    pcs = get_pcs_scraper()
    if pcs:
        try:
            teams_df = pcs.teams_by_year(year=year, gender=gender)
            if teams_df is not None and not teams_df.empty:
                for _, row in teams_df.iterrows():
                    name = str(row.get('team', '')).strip()
                    if not name:
                        continue
                    team_slug = slugify(name)
                    Team.objects.update_or_create(
                        slug=team_slug, year=year,
                        defaults={
                            'name': name,
                            'nationality': str(row.get('nationality', '')).strip()[:3],
                            'status': str(row.get('class', 'Continental'))[:20],
                        }
                    )
                return Team.objects.filter(year=year)
        except Exception as exc:
            logger.warning("pcs_scraper teams_by_year failed for %s: %s", year, exc)

    soup = pcs_get(f"{PCS_BASE_URL}/teams.php?year={year}&s=worldtour")
    if soup:
        _parse_and_save_teams(soup, year)
    return Team.objects.filter(year=year).order_by('name')


def fetch_team_detail(team_slug, year):
    """Fetch detailed team data and save to database."""
    from teams.models import Team
    pcs = get_pcs_scraper()
    riders_df = None
    if pcs:
        try:
            team_obj = pcs.Team(name=team_slug, year=year)
            riders_df = team_obj.get_riders()
        except Exception as exc:
            logger.warning("pcs_scraper Team failed for %s %s: %s", team_slug, year, exc)

    soup = pcs_get(f"{PCS_BASE_URL}/team/{team_slug}/{year}")
    team_data = _parse_team_page(soup, team_slug, year) if soup else {}

    team, created = Team.objects.update_or_create(
        slug=team_slug, year=year,
        defaults=team_data if team_data else {'name': team_slug.replace('-', ' ').title(), 'year': year}
    )

    if riders_df is not None and not riders_df.empty:
        _save_team_riders(team, riders_df)
    elif soup:
        _parse_and_save_team_riders(team, soup)

    return team


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
        data['pcs_url'] = f"{PCS_BASE_URL}/team/{team_slug}/{year}"

        img = soup.find('img', class_='teamlogo')
        if img and img.get('src'):
            src = img['src']
            data['logo_url'] = src if src.startswith('http') else PCS_BASE_URL + src

        for li in soup.select('ul.infolist li'):
            spans = li.find_all('span')
            if len(spans) >= 2:
                key = spans[0].get_text(strip=True).lower()
                val = spans[1].get_text(strip=True)
                if 'country' in key or 'nation' in key:
                    data['country_name'] = val
                elif 'bike' in key:
                    data['bike_brand'] = val[:100]
                elif 'clothing' in key or 'kit' in key:
                    data['clothing_brand'] = val[:100]
                elif 'manager' in key or 'directeur' in key:
                    data['manager'] = val[:200]
    except Exception as exc:
        logger.error("Error parsing team page %s %s: %s", team_slug, year, exc)
    return data


def _parse_and_save_teams(soup, year):
    """Parse teams list page and save to database."""
    from teams.models import Team
    try:
        for row in soup.select('ul.list.teams li'):
            link = row.find('a')
            if not link:
                continue
            name = link.get_text(strip=True)
            href = link.get('href', '')
            slug = href.split('/team/')[-1].split('/')[0] if '/team/' in href else slugify(name)
            Team.objects.update_or_create(
                slug=slug, year=year,
                defaults={'name': name, 'year': year}
            )
    except Exception as exc:
        logger.error("Error parsing teams list: %s", exc)


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
        for a in soup.select('a[href*="/rider/"]'):
            rider_name = a.get_text(strip=True)
            href = a.get('href', '')
            rider_slug = href.split('/rider/')[-1].strip('/')
            if not rider_slug or not rider_name:
                continue
            rider, _ = Rider.objects.get_or_create(
                slug=rider_slug,
                defaults={'name': rider_name}
            )
            TeamRoster.objects.get_or_create(team=team, rider=rider)
    except Exception as exc:
        logger.error("Error parsing team riders: %s", exc)
