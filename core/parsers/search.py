"""Parser des résultats de recherche PCS (search.php)."""
import re

from core.parsers.common import slug_from_href, team_slug_year_from_href

_YEAR_RE = re.compile(r'/(\d{4})(?:/|$)')


def parse_search(soup, limit=8):
    """Parse la zone content de search.php → {riders, teams, races}.

    Chaque entrée : {'name', 'slug', 'url'(+'year' pour course/équipe)}.
    """
    content = soup.find('div', class_='content') or soup
    riders, teams, races = [], [], []
    seen = set()
    for a in content.find_all('a', href=True):
        href = a['href'].lstrip('/')
        text = a.get_text(' ', strip=True)
        if not text:
            continue
        # Nettoie le texte (PCS ajoute date/âge après un |)
        name = text.split('|')[0].strip()
        if href.startswith('rider/') and len(riders) < limit:
            slug = slug_from_href(href, 'rider')
            key = ('r', slug)
            if slug and key not in seen:
                seen.add(key)
                riders.append({'type': 'rider', 'name': name, 'slug': slug})
        elif href.startswith('team/') and len(teams) < limit:
            slug, year = team_slug_year_from_href(href)
            key = ('t', slug, year)
            if slug and key not in seen:
                seen.add(key)
                teams.append({'type': 'team', 'name': name, 'slug': slug, 'year': year})
        elif href.startswith('race/') and len(races) < limit:
            slug = slug_from_href(href, 'race')
            m = _YEAR_RE.search('/' + href)
            year = int(m.group(1)) if m else None
            key = ('c', slug, year)
            if slug and year and key not in seen:
                seen.add(key)
                races.append({'type': 'race', 'name': name, 'slug': slug, 'year': year})
    return {'riders': riders, 'teams': teams, 'races': races}
