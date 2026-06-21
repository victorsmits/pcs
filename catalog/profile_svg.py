"""Construit les données SVG du profil d'étape (silhouette + échelle)."""
from core.parsers.profile import points_to_svg

VIEW_W = 1000
VIEW_H = 200


def _nice_step(span, target_ticks=5):
    """Renvoie un pas « rond » pour ~target_ticks graduations sur une étendue donnée."""
    if span <= 0:
        return 1
    raw = span / target_ticks
    import math
    mag = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 2.5, 5, 10):
        if raw <= mult * mag:
            return mult * mag
    return 10 * mag


def build_profile_svg(elevation_points, min_ele=None, max_ele=None, max_km=None, climbs=None):
    """Renvoie un dict prêt pour le template (ou None si pas de données).

    Inclut polyline/area + graduations d'altitude (y_ticks) et de distance (x_ticks).
    """
    if not elevation_points:
        return None
    polyline, area = points_to_svg(elevation_points, VIEW_W, VIEW_H)
    if not polyline:
        return None

    # Graduations d'altitude. Avec min/max connus → labels en mètres ;
    # sinon (profil extrait d'image) → lignes de grille sans valeurs.
    y_ticks = []
    has_meters = min_ele is not None and max_ele is not None and max_ele > min_ele
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        label = ''
        if has_meters:
            label = f'{round(min_ele + frac * (max_ele - min_ele))} m'
        y_ticks.append({'top_pct': round((1 - frac) * 100, 2), 'label': label})

    # Graduations de distance
    x_ticks = []
    if max_km:
        step = _nice_step(max_km, 5)
        km = 0.0
        while km <= max_km + 0.01:
            x_ticks.append({'left_pct': round(km / max_km * 100, 2),
                            'label': f'{int(km)}'})
            km += step

    climb_markers = []
    for c in (climbs or []):
        km = c.get('km')
        if km is None or not max_km:
            continue
        climb_markers.append({
            'left_pct': round(km / max_km * 100, 1),
            'name': c.get('name', ''),
            'category': c.get('category', ''),
        })

    return {
        'width': VIEW_W,
        'height': VIEW_H,
        'polyline': polyline,
        'area': area,
        'y_ticks': y_ticks,
        'x_ticks': x_ticks,
        'climbs': climb_markers,
        'max_km': max_km,
    }
