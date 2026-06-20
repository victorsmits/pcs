"""Parser de page équipe PCS."""
import re

from core.parsers.common import slug_from_href

_LEVEL_RE = re.compile(r'\(([A-Z]{2,3})\)\s*$')


def parse_team(soup):
    """Extrait infos + effectif d'une page équipe. Renvoie un dict."""
    data = {'name': '', 'level': '', 'nationality': '', 'roster': [], 'stats': {}}

    h1 = soup.find('h1')
    if h1:
        raw = h1.get_text(' ', strip=True)
        m = _LEVEL_RE.search(raw)
        if m:
            data['level'] = m.group(1)
            raw = _LEVEL_RE.sub('', raw).strip()
        data['name'] = raw

    title = soup.find('div', class_='titleCont') or soup.find('div', class_='page-title')
    flag = (title.find('span', class_='flag') if title else None)
    if flag:
        cls = flag.get('class', [])
        code = next((c for c in cls if c != 'flag' and len(c) == 2), None)
        if code:
            data['nationality'] = code

    # Stats (Victories / Points / PCS# / UCI#) — sur tout le texte d'en-tête
    info_text = (title.get_text(' ', strip=True) if title else '')
    if 'Points' not in info_text:
        info_text = soup.get_text(' ', strip=True)[:2000]
    for label, key in (('Victories', 'wins'), ('Points', 'points'),
                       ('PCS#', 'pcs_rank'), ('UCI#', 'uci_rank')):
        m = re.search(re.escape(label) + r'\s*(\d+)', info_text)
        if m:
            data['stats'][key] = int(m.group(1))

    # Effectif : table.teamlist
    roster_table = soup.find('table', class_='teamlist')
    if roster_table:
        for a in roster_table.find_all('a', href=re.compile(r'rider/')):
            name = a.get_text(' ', strip=True)
            if not name:
                continue
            data['roster'].append({'name': name, 'slug': slug_from_href(a.get('href'), 'rider')})

    return data
