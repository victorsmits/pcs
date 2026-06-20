"""Construit les données SVG du profil d'étape à partir des points d'altitude."""
from core.parsers.profile import points_to_svg

VIEW_W = 1000
VIEW_H = 200


def build_profile_svg(elevation_points, climbs=None):
    """Renvoie un dict prêt pour le template (ou None si pas de données).

    {
      'width', 'height', 'polyline', 'area',
      'climbs': [{'x', 'name', 'category'}…]
    }
    """
    if not elevation_points:
        return None
    polyline, area = points_to_svg(elevation_points, VIEW_W, VIEW_H)
    if not polyline:
        return None

    climb_markers = []
    for c in (climbs or []):
        km = c.get('km')
        max_km = c.get('max_km')
        if km is None or not max_km:
            continue
        climb_markers.append({
            'x': round(km / max_km * VIEW_W, 1),
            'name': c.get('name', ''),
            'category': c.get('category', ''),
        })

    return {
        'width': VIEW_W,
        'height': VIEW_H,
        'polyline': polyline,
        'area': area,
        'climbs': climb_markers,
    }
