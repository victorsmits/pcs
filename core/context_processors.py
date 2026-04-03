from datetime import date


def global_context(request):
    current_year = date.today().year
    return {
        'current_year': current_year,
        'years_range': list(range(current_year, 1999, -1)),
        'nav_years': list(range(current_year, current_year - 5, -1)),
        'app_name': 'CycloStats',
        'app_tagline': 'La référence du cyclisme professionnel',
    }
