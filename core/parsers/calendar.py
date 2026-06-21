"""Parser du calendrier PCS (races.php)."""
from core.parsers.common import (
    clean_name, slug_from_href, parse_pcs_date, classification_flags,
)


def parse_calendar(soup, year):
    """Parse une page races.php → liste de dicts course.

    Colonnes PCS : [Date (plage), Date (début), Race, Winner, Class].
    """
    races = []
    table = soup.find('table')
    if not table:
        return races

    for row in table.select('tbody tr'):
        cells = row.find_all('td')
        if len(cells) < 3:
            continue

        # Lien course (cherche un <a href="race/...">)
        race_link = row.find('a', href=lambda h: h and h.lstrip('/').startswith('race/'))
        if not race_link:
            continue
        slug = slug_from_href(race_link.get('href'), 'race')
        if not slug:
            continue

        name = clean_name(race_link.get_text(strip=True), year)

        # Plage de dates : 1re cellule
        date_text = cells[0].get_text(' ', strip=True)
        start_date, end_date = parse_pcs_date(date_text, year)

        # Classification : dernière cellule
        classification = cells[-1].get_text(strip=True)

        # Vainqueur (rider link), si présent
        winner_link = row.find('a', href=lambda h: h and h.lstrip('/').startswith('rider/'))
        winner_slug = slug_from_href(winner_link.get('href'), 'rider') if winner_link else ''
        winner_name = clean_name(winner_link.get_text(strip=True)) if winner_link else ''

        is_stage, is_gt, is_mon = classification_flags(slug, classification)

        races.append({
            'slug': slug,
            'year': year,
            'name': name or slug.replace('-', ' ').title(),
            'classification': classification,
            'start_date': start_date,
            'end_date': end_date,
            'is_stage_race': is_stage,
            'is_grand_tour': is_gt,
            'is_monument': is_mon,
            'winner_slug': winner_slug,
            'winner_name': winner_name,
        })

    return races
