"""Parser de page coureur PCS."""
import re
from datetime import date

from core.parsers.common import slug_from_href

_MONTHS = {m: i for i, m in enumerate(
    ['january', 'february', 'march', 'april', 'may', 'june', 'july',
     'august', 'september', 'october', 'november', 'december'], 1)}


def _parse_birthdate(text):
    m = re.search(r'(\d{1,2})\w{0,2}\s+([A-Za-z]+)\s+(\d{4})', text)
    if not m:
        return None
    day, mon, year = int(m.group(1)), _MONTHS.get(m.group(2).lower()), int(m.group(3))
    if not mon:
        return None
    try:
        return date(year, mon, day)
    except ValueError:
        return None


def parse_rider(soup):
    """Extrait infos + palmarès d'une page coureur. Renvoie un dict."""
    data = {'name': '', 'nationality': '', 'birthdate': None, 'weight': None,
            'height': None, 'photo_url': '', 'specialties': {}, 'pcs_rank': None,
            'team_name': '', 'team_slug': '', 'top_results': []}

    h1 = soup.find('h1')
    if h1:
        data['name'] = h1.get_text(' ', strip=True)

    title = soup.find('div', class_='titleCont') or soup.find('div', class_='page-title')
    content = soup.find('div', class_='content') or soup

    # Bloc info (texte)
    info_text = ''
    for el in content.find_all(['ul', 'div']):
        t = el.get_text(' ', strip=True)
        if 'Date of birth' in t and len(t) < 600:
            info_text = t
            break

    if info_text:
        data['birthdate'] = _parse_birthdate(info_text)
        m = re.search(r'Weight:\s*([\d.]+)', info_text)
        if m:
            data['weight'] = float(m.group(1))
        m = re.search(r'Height:\s*([\d.]+)', info_text)
        if m:
            data['height'] = float(m.group(1))
        m = re.search(r'Nationality:\s*([A-Za-zÀ-ÿ\- ]+?)\s+(?:Weight|Height|Place|Specialties|$)', info_text)
        if m:
            data['nationality_name'] = m.group(1).strip()

    # Code nationalité (drapeau dans l'en-tête, pas le sélecteur de langue)
    flag = (title.find('span', class_='flag') if title else None)
    if flag:
        cls = flag.get('class', [])
        code = next((c for c in cls if c not in ('flag',) and len(c) == 2), None)
        if code:
            data['nationality'] = code

    # Photo
    img = soup.find('img', src=re.compile(r'riders/'))
    if img:
        src = img['src'].split('?')[0]
        data['photo_url'] = src if src.startswith('http') else f'https://www.procyclingstats.com/{src.lstrip("/")}'

    # Équipe courante (1er lien équipe du contenu principal)
    team_link = content.find('a', href=re.compile(r'team/'))
    if team_link:
        from core.parsers.common import team_slug_year_from_href
        data['team_slug'], _ = team_slug_year_from_href(team_link.get('href'))
        data['team_name'] = team_link.get_text(' ', strip=True)

    # Points par spécialité (Onedayraces / GC / TT / Sprint / Climber / Hills)
    for label in ('Onedayraces', 'GC', 'TT', 'Sprint', 'Climber', 'Hills'):
        m = re.search(r'(\d+)\s*' + label, info_text)
        if m:
            data['specialties'][label.lower()] = int(m.group(1))

    m = re.search(r'PCS Ranking\s*(\d+)', info_text)
    if m:
        data['pcs_rank'] = int(m.group(1))

    # Top résultats (table avec colonnes Date / #Result / Race)
    for table in soup.find_all('table'):
        head = [th.get_text(strip=True).lower() for th in table.select('thead th')]
        if 'race' in head and ('#result' in head or 'result' in head):
            for row in table.select('tbody tr')[:25]:
                race_link = row.find('a', href=re.compile(r'race/'))
                if not race_link:
                    continue
                cells = row.find_all('td')
                rank = ''
                for c in cells[:3]:
                    txt = c.get_text(strip=True)
                    if txt.isdigit():
                        rank = txt
                        break
                data['top_results'].append({
                    'date': cells[0].get_text(strip=True) if cells else '',
                    'rank': rank,
                    'race': race_link.get_text(' ', strip=True),
                    'race_href': race_link.get('href', ''),
                })
            break

    return data
