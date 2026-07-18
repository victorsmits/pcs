"""Parser du classement PCS (rankings/{me,we}/individual)."""

from core.parsers.common import slug_from_href, parse_int


def parse_pcs_ranking(soup, limit=100):
    """Parse une page de classement PCS individuel → liste de dicts.

    [{rank, previous_rank, rider_name, rider_slug, team_name, team_slug, team_year, points}]
    """
    table = soup.find('table', class_='basic') or soup.find('table')
    if not table:
        return []
    out = []
    rows = table.select('tbody tr') or table.find_all('tr')[1:]
    for row in rows[:limit]:
        cells = row.find_all('td')
        if not cells:
            continue
        rank = parse_int(cells[0].get_text())
        if rank is None:
            continue
        rider_link = row.find('a', href=lambda h: h and 'rider/' in h)
        if not rider_link:
            continue
        team_link = row.find('a', href=lambda h: h and 'team/' in h)
        from core.parsers.common import team_slug_year_from_href
        team_slug, team_year = team_slug_year_from_href(team_link.get('href')) if team_link else ('', None)
        # Points = dernière cellule numérique
        points = None
        for c in reversed(cells):
            v = parse_int(c.get_text())
            if v is not None:
                points = v
                break
        prev = parse_int(cells[1].get_text()) if len(cells) > 1 else None
        out.append({
            'rank': rank,
            'previous_rank': prev,
            'rider_name': rider_link.get_text(' ', strip=True),
            'rider_slug': slug_from_href(rider_link.get('href'), 'rider'),
            'team_name': team_link.get_text(' ', strip=True) if team_link else '',
            'team_slug': team_slug, 'team_year': team_year,
            'points': points or 0,
        })
    return out
