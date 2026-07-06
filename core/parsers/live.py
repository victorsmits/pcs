"""Parser de la page live PCS : objet `data`, situation (groupes), timeline."""
import json
import re

from bs4 import BeautifulSoup

from core.parsers.common import slug_from_href

_DATA_RE = re.compile(r'var data = (\{.*?\});', re.DOTALL)
_GAP_RE = re.compile(r'\+\d+:\d+')
_TIMER_RE = re.compile(r'\b\d+[smh]\b')  # "9s", "2m", "1h" → timers PCS à supprimer


def _clean_event_html(cont):
    """Reconstruit un HTML propre depuis .cont PCS : texte + liens coureurs.

    Supprime les timers PCS (9s, 2m…) et les balises parasites,
    garde uniquement le texte et les <a href="rider/..."> .
    """
    if not cont:
        return ''
    from bs4 import NavigableString, Tag

    parts = []

    def walk(node):
        if isinstance(node, NavigableString):
            t = str(node)
            if t.strip():
                parts.append(t)
        elif isinstance(node, Tag):
            if node.name == 'a' and 'rider/' in (node.get('href') or ''):
                parts.append(str(node))
            elif node.name == 'br':
                parts.append(' ')
            else:
                for child in node.children:
                    walk(child)

    walk(cont)
    raw = ''.join(parts)
    # Supprime les timers PCS standalone ("9s", "2m"…) entourés d'espaces
    raw = _TIMER_RE.sub('', raw)
    return re.sub(r' {2,}', ' ', raw).strip()


def parse_live_data(html):
    """Extrait l'objet JS `var data = {...}` de la page live → dict (ou {})."""
    m = _DATA_RE.search(html)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except (ValueError, json.JSONDecodeError):
        return {}


def live_state_from_data(data):
    """Mappe l'objet `data` vers les champs d'un LiveSession."""
    status = (data.get('race_status') or 'unknown').lower()
    if status not in ('preview', 'racing', 'finished'):
        status = 'unknown'
    finished = bool(data.get('finished'))
    km_done = data.get('kmdone') or 0
    max_km = data.get('maxkm')
    km_to_go = data.get('kmtogo')
    # Avant le départ, PCS renvoie kmtogo=0 → on affiche la distance restante réelle.
    if not finished and (not km_to_go) and max_km:
        km_to_go = round(max_km - km_done, 1)
    return {
        'pcs_live_id': data.get('ls_pid'),
        'race_status': status,
        'km_done': km_done,
        'km_to_go': km_to_go,
        'max_km': max_km,
        'perc': data.get('perc'),
        'avg_speed': data.get('avg') or data.get('avg_speed') or 0,
        'min_ele': data.get('min_ele'),
        'max_ele': data.get('max_ele'),
        'started_ts': data.get('started_ts'),
        'start_time': data.get('start_time_cet') or data.get('start_time') or '',
        'finished': finished,
    }


_KP_CLIMB = 1   # col catégorisé
_KP_SPRINT = 2  # sprint intermédiaire


def keypoints_from_data(data):
    """Liste des points clés (cols/sprints) depuis data['keypoints'].

    Seuls type=1 (col) et type=2 (sprint) sont retenus.
    Les type=6 (villes) et type=9 (frontières) sont ignorés.
    """
    out = []
    max_km = data.get('maxkm')
    for kp in data.get('keypoints', []) or []:
        if kp.get('type') not in (_KP_CLIMB, _KP_SPRINT):
            continue
        km = kp.get('km')
        out.append({
            'name': kp.get('title') or '',
            'km': km,
            'length': kp.get('lengte') or None,
            'avg_grad': kp.get('avg_perc') or None,
            'category': str(kp.get('category') or ''),
            'url': kp.get('url') or '',
            'x': round(km / max_km * 100, 2) if (km is not None and max_km) else None,
        })
    return out


def parse_groups(soup):
    """Parse la situation de course → liste de groupes ordonnés (tête → arrière)."""
    situ = soup.find(class_='situCont') or soup.find(class_=re.compile(r'\bsitu', re.I))
    if not situ:
        return []
    groups = []
    for i, g in enumerate(situ.find_all(class_='group')):
        name_el = g.find(class_='groupname')
        label = name_el.get_text(' ', strip=True) if name_el else ''
        time_el = g.find(class_='time')
        gap_text = time_el.get_text(' ', strip=True) if time_el else ''
        gap_m = _GAP_RE.search(gap_text)
        gap = gap_m.group() if gap_m else ''

        riders = []
        for a in g.find_all('a', href=re.compile(r'rider/')):
            riders.append({'name': a.get_text(strip=True), 'slug': slug_from_href(a.get('href'), 'rider')})

        if not label:
            label = 'Tête de course' if i == 0 else f'Groupe {i + 1}'

        groups.append({
            'order': i,
            'label': label,
            'gap': gap,
            'rider_count': len(riders),
            'riders': riders,
        })
    return groups


def parse_timeline(soup, limit=60):
    """Parse la timeline d'événements → liste [{seqnr, marker, text, html}] (récents d'abord)."""
    ul = soup.find('ul', class_=re.compile('timeline'))
    if not ul:
        return []
    events = []
    for li in ul.find_all('li', recursive=False)[:limit]:
        seqnr = li.get('data-seqnr')
        bol = li.find(class_='bol')
        cont = li.find(class_='cont')
        marker = bol.get_text(strip=True) if bol else ''
        text = cont.get_text(' ', strip=True) if cont else li.get_text(' ', strip=True)
        events.append({
            'seqnr': int(seqnr) if seqnr and seqnr.isdigit() else None,
            'marker': marker[:40],
            'text': text[:500],
            'html': _clean_event_html(cont)[:3000],
        })
    return events


def parse_live_page(html):
    """Parse complet de la page live. Renvoie un dict agrégé."""
    soup = BeautifulSoup(html, 'lxml')
    data = parse_live_data(html)
    return {
        'data': data,
        'state': live_state_from_data(data) if data else {},
        'keypoints': keypoints_from_data(data) if data else [],
        'groups': parse_groups(soup),
        'timeline': parse_timeline(soup),
    }
