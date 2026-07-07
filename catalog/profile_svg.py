"""Construit les données du profil d'étape pour le template Chart.js."""


def _nice_step(span, target_ticks=5):
    """Renvoie un pas « rond » pour ~target_ticks graduations sur une étendue donnée."""
    if span <= 0:
        return 1
    import math
    raw = span / target_ticks
    mag = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 2.5, 5, 10):
        if raw <= mult * mag:
            return mult * mag
    return 10 * mag


def build_profile_svg(elevation_points, min_ele=None, max_ele=None, max_km=None, climbs=None):
    """Renvoie un dict prêt pour le template Chart.js (ou None si pas de données)."""
    if not elevation_points:
        return None

    # Estimation de max_km depuis les cols si absent
    effective_max_km = max_km
    if not effective_max_km and climbs:
        kms = [c.get('km') for c in climbs if c.get('km') is not None]
        if kms:
            effective_max_km = max(kms)

    climb_markers = []
    for c in (climbs or []):
        km = c.get('km')
        if km is None or not effective_max_km:
            continue
        climb_markers.append({
            'left_pct': round(km / effective_max_km * 100, 1),
            'km': km,
            'name': c.get('name', ''),
            'category': c.get('category', ''),
        })

    return {
        'raw_points': elevation_points,
        'min_ele': min_ele,
        'max_ele': max_ele,
        'max_km': max_km,
        'climbs': climb_markers,
    }
