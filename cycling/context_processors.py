from datetime import date


def global_context(request):
    current_year = date.today().year
    try:
        from cycling.scraper import find_ongoing_races
        ongoing_races = find_ongoing_races()[:3]
    except Exception:
        ongoing_races = []
    return {
        'current_year': current_year,
        'nav_years': list(range(current_year, current_year - 5, -1)),
        'ongoing_races': ongoing_races,
        'app_name': 'CycloStats',
    }
