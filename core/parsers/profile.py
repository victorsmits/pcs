"""Extraction du profil d'altitude (polygone clip-path PCS) → points SVG."""
import re

_POLY_RE = re.compile(r'clip-path:\s*polygon\(([^)]+)\)')


def extract_elevation_points(html):
    """Extrait les points d'altitude depuis le `clip-path: polygon(...)` de la page live.

    Renvoie une liste [[x, h], …] où x ∈ [0,100] (avancée le long de l'étape) et
    h ∈ [0,100] (hauteur relative, 0 = bas, 100 = sommet). Les coins de fermeture
    du polygone sont écartés.
    """
    if hasattr(html, 'decode_contents'):
        html = str(html)
    m = _POLY_RE.search(html)
    if not m:
        return []

    points = []
    for token in m.group(1).split(','):
        parts = token.strip().split()
        if len(parts) != 2:
            continue
        try:
            x = float(parts[0].replace('%', ''))
            y = float(parts[1].replace('%', ''))
        except ValueError:
            continue
        # Coins de fermeture : (0,100)=bas-gauche, (100,0)=haut-droite, (0,0)=haut-gauche
        if (x == 0 and y in (0.0, 100.0)) or (x == 100 and y == 0):
            continue
        h = round(100.0 - y, 3)   # y% est mesuré depuis le haut → on inverse
        points.append([round(x, 3), h])

    points.sort(key=lambda p: p[0])
    return points


def points_to_svg(points, width=1000, height=200, pad_top=6):
    """Convertit [[x,h],…] en attributs SVG : (polyline_points, area_path)."""
    if not points:
        return '', ''
    usable = height - pad_top
    coords = []
    for x, h in points:
        sx = round(x / 100.0 * width, 2)
        sy = round(height - (h / 100.0 * usable), 2)
        coords.append((sx, sy))
    polyline = ' '.join(f'{x},{y}' for x, y in coords)
    area = (f'M {coords[0][0]},{height} '
            + ' '.join(f'L {x},{y}' for x, y in coords)
            + f' L {coords[-1][0]},{height} Z')
    return polyline, area
