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


_STAGE_LINK_RE = re.compile(r'/race/[^/]+/\d+/stage-(\d+)\b')


def parse_stage_list(soup):
    """Depuis une page course (overview), liste les étapes : [{number, departure, arrival}]."""
    stages = {}
    for a in soup.find_all('a', href=True):
        m = _STAGE_LINK_RE.search('/' + a['href'].lstrip('/'))
        if not m:
            continue
        number = int(m.group(1))
        if number in stages:
            continue
        text = a.get_text(' ', strip=True)
        departure = arrival = ''
        # "Stage 1 | Velenje - Rogaška Slatina"
        if '|' in text:
            _, _, route = text.partition('|')
            route = route.strip()
            if ' - ' in route:
                departure, _, arrival = route.partition(' - ')
        stages[number] = {
            'number': number,
            'departure': departure.strip(),
            'arrival': arrival.strip(),
        }
    return [stages[k] for k in sorted(stages)]
