"""Parser générique de tables de résultats PCS (étape, GC, points, kom…)."""
import re

from core.parsers.common import slug_from_href, team_slug_year_from_href

_STATUS = {'dnf': 'dnf', 'dns': 'dns', 'otl': 'otl', 'dsq': 'dsq', 'df': 'ok'}


def _header_map(table):
    """Mappe nom de colonne (minuscule) → index."""
    heads = table.select('thead th')
    mapping = {}
    for i, th in enumerate(heads):
        key = th.get_text(strip=True).lower()
        if key:
            mapping[key] = i
    return mapping


def parse_results_table(soup_or_table, limit=200):
    """Parse une table.results → liste de dicts.

    Chaque dict : rank, status, rider_slug, rider_name, team_slug, team_year,
    time, time_gap, points_uci, points_pcs, nat.
    """
    table = soup_or_table if getattr(soup_or_table, 'name', None) == 'table' \
        else (soup_or_table.find('table', class_='results') if soup_or_table else None)
    if not table:
        return []

    cols = _header_map(table)
    results = []
    for row in table.select('tbody tr')[:limit]:
        cells = row.find_all('td')
        if not cells:
            continue

        def cell(name):
            idx = cols.get(name)
            return cells[idx] if idx is not None and idx < len(cells) else None

        rank_txt = (cell('rnk') or cells[0]).get_text(strip=True)
        status = 'ok'
        rank = None
        if rank_txt.isdigit():
            rank = int(rank_txt)
        elif rank_txt.lower() in _STATUS:
            status = _STATUS[rank_txt.lower()]

        rider_link = row.find('a', href=lambda h: h and 'rider/' in h)
        if not rider_link:
            continue
        rider_slug = slug_from_href(rider_link.get('href'), 'rider')
        rider_name = rider_link.get_text(' ', strip=True)

        team_link = row.find('a', href=lambda h: h and 'team/' in h)
        team_slug, team_year = team_slug_year_from_href(team_link.get('href')) if team_link else ('', None)
        team_name = team_link.get_text(' ', strip=True) if team_link else ''

        time_cell = cell('time')
        time_val = time_cell.get_text(' ', strip=True).split()[0] if time_cell and time_cell.get_text(strip=True) else ''
        gap_cell = cell('timelag') or cell('gc time') or cell('gc')
        gap = gap_cell.get_text(strip=True) if gap_cell else ''

        def num(name):
            c = cell(name)
            if not c:
                return None
            m = re.search(r'\d+', c.get_text())
            return int(m.group()) if m else None

        flag = row.find('span', class_='flag')
        nat = ''
        if flag:
            classes = flag.get('class', [])
            nat = classes[1] if len(classes) > 1 else ''

        results.append({
            'rank': rank, 'status': status,
            'rider_slug': rider_slug, 'rider_name': rider_name,
            'team_slug': team_slug, 'team_year': team_year, 'team_name': team_name,
            'time': time_val, 'time_gap': gap,
            'points_uci': num('uci'), 'points_pcs': num('pnt'),
            'nat': nat,
        })
    return results
