"""Parsers de page étape PCS : bloc « Race information », image profil."""
import re

from core.parsers.common import parse_float, parse_int, clean_name


def _info_dict(soup):
    """Construit un dict {label: valeur} depuis l'infolist d'une page étape/course."""
    info = {}
    for ul in soup.find_all('ul'):
        classes = ul.get('class') or []
        if 'keyvalueList' not in classes and 'infolist' not in classes:
            continue
        for li in ul.find_all('li', recursive=False):
            text = li.get_text(' ', strip=True)
            if ':' in text:
                label, _, value = text.partition(':')
                info[label.strip().lower()] = value.strip()
        if info:
            break
    return info


_STAGE_TYPE_MAP = [
    ('mountain', 'mountains_uphill'),
    ('hill', 'hills_uphill'),
    ('flat', 'flat'),
]


def parse_stage_info(soup):
    """Extrait les infos d'une page étape. Renvoie un dict prêt pour le modèle Stage."""
    info = _info_dict(soup)
    data = {}

    if 'distance' in info:
        data['distance'] = parse_float(info['distance'])
    if 'vertical meters' in info:
        data['vertical_meters'] = parse_int(info['vertical meters'])
    if 'profilescore' in info:
        data['profile_score'] = parse_int(info['profilescore'])
    if 'gradient final km' in info:
        data['gradient_final'] = parse_float(info['gradient final km'])
    if 'departure' in info:
        data['departure'] = info['departure']
    if 'arrival' in info:
        data['arrival'] = info['arrival']

    # Image profil (JPG hébergé)
    img = soup.find('img', src=re.compile(r'images/profiles/.+\.(jpg|png)', re.I))
    if img:
        src = img.get('src')
        data['profile_image_url'] = src if src.startswith('http') else f'https://www.procyclingstats.com/{src.lstrip("/")}'

    return data


def parse_stage_images(soup):
    """Depuis la page /info/profiles d'une étape, extrait profil/carte/arrivée.

    Renvoie {'profile_image_url', 'map_image_url', 'finish_image_url'} (URLs absolues).
    """
    base = 'https://www.procyclingstats.com'
    out = {}
    for img in soup.find_all('img', src=True):
        src = img['src'].split('?')[0]
        if 'images/profiles/' not in src:
            continue
        url = src if src.startswith('http') else f'{base}/{src.lstrip("/")}'
        low = src.lower()
        if '-map' in low and 'map_image_url' not in out:
            out['map_image_url'] = url
        elif '-finish' in low and 'finish_image_url' not in out:
            out['finish_image_url'] = url
        elif 'profile_image_url' not in out:
            out['profile_image_url'] = url
    return out


_STAGE_LINK_RE = re.compile(r'/?race/[^/]+/\d+/stage-(\d+)\b')


def _route_from_text(text):
    departure = arrival = ''
    if '|' in text:
        _, _, route = text.partition('|')
        route = route.strip()
        if ' - ' in route:
            departure, _, arrival = route.partition(' - ')
    return departure.strip(), arrival.strip()


def parse_stage_list(soup, year=None):
    """Depuis une page course (overview), liste les étapes avec date/distance.

    Renvoie [{number, departure, arrival, date, distance}].
    """
    from core.parsers.common import parse_pcs_date, parse_float
    stages = {}

    # 1) Table d'étapes (Date | Day | icône | Stage | KM)
    for table in soup.find_all('table'):
        link = table.find('a', href=_STAGE_LINK_RE)
        if not link:
            continue
        for row in table.select('tbody tr'):
            a = row.find('a', href=_STAGE_LINK_RE)
            if not a:
                continue
            m = _STAGE_LINK_RE.search('/' + a['href'].lstrip('/'))
            number = int(m.group(1))
            cells = row.find_all('td')
            date = None
            distance = None
            if cells:
                d, _ = parse_pcs_date(cells[0].get_text(strip=True).replace('/', '.'), year) if year else (None, None)
                date = d
                distance = parse_float(cells[-1].get_text(strip=True))
            dep, arr = _route_from_text(a.get_text(' ', strip=True))
            stages[number] = {'number': number, 'departure': dep, 'arrival': arr,
                              'date': date, 'distance': distance}
        if stages:
            break

    # 2) Repli : scan des liens
    if not stages:
        for a in soup.find_all('a', href=_STAGE_LINK_RE):
            m = _STAGE_LINK_RE.search('/' + a['href'].lstrip('/'))
            number = int(m.group(1))
            if number in stages:
                continue
            dep, arr = _route_from_text(a.get_text(' ', strip=True))
            stages[number] = {'number': number, 'departure': dep, 'arrival': arr,
                              'date': None, 'distance': None}

    return [stages[k] for k in sorted(stages)]


def parse_jersey_wearers(soup):
    """Liste des porteurs de maillots après une étape (1er = leader général).

    Renvoie [{'name', 'slug'}] dans l'ordre PCS (général, points, montagne, jeunes…).
    """
    from core.parsers.common import slug_from_href
    block = None
    for el in soup.find_all('div'):
        txt = el.get_text(' ', strip=True)
        if txt.startswith('Jersey wearers') and len(txt) < 200:
            block = el
            break
    if not block:
        return []
    seen, out = set(), []
    for a in block.find_all('a', href=re.compile(r'rider/')):
        slug = slug_from_href(a.get('href'), 'rider')
        if slug and slug not in seen:
            seen.add(slug)
            out.append({'name': a.get_text(' ', strip=True), 'slug': slug})
    return out


def parse_stage_winners(soup):
    """Table « Stage winners » → {numéro: {'name', 'slug'}}."""
    from core.parsers.common import slug_from_href
    winners = {}
    for table in soup.find_all('table'):
        head = [th.get_text(strip=True).lower() for th in table.select('thead th')]
        if 'stage' in head and 'winner' in head:
            for row in table.select('tbody tr'):
                cells = row.find_all('td')
                if len(cells) < 2:
                    continue
                mnum = re.search(r'\d+', cells[0].get_text())
                a = cells[1].find('a', href=re.compile(r'rider/'))
                if mnum and a:
                    winners[int(mnum.group())] = {
                        'name': a.get_text(strip=True),
                        'slug': slug_from_href(a.get('href'), 'rider'),
                    }
            break
    return winners
