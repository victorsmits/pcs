"""Extraction de la silhouette d'altitude depuis une image de profil PCS.

Les profils PCS sont des images où l'aire sous la courbe d'altitude est remplie
en vert sur fond blanc. On scanne chaque colonne pour trouver le sommet du vert
→ points d'altitude relatifs [[x%, h%]], comme le polygone des pages live.
"""
import io
import logging

logger = logging.getLogger('core')


def _is_fill(p):
    """Pixel appartenant à la silhouette (vert PCS, clair ou foncé)."""
    r, g, b = p[0], p[1], p[2]
    return g > 110 and g >= r - 10 and g > b + 25


def extract_elevation_from_image(image_bytes, samples=180):
    """Renvoie une liste [[x%, h%], …] extraite de l'image, ou [] si échec."""
    try:
        from PIL import Image
    except ImportError:
        return []
    try:
        im = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    except Exception:  # noqa: BLE001
        return []

    w, h = im.size
    if w < 50 or h < 30:
        return []
    px = im.load()

    # Bounding box de la zone verte (silhouette)
    step = max(1, w // 400)
    xs, ys = [], []
    for x in range(0, w, step):
        for y in range(0, h, max(1, h // 200)):
            if _is_fill(px[x, y]):
                xs.append(x)
                ys.append(y)
                break
    if len(xs) < 20:
        return []
    x0, x1 = min(xs), max(xs)
    # baseline = bas de la silhouette (on balaye depuis le bas)
    y_bottom = 0
    for x in range(x0, x1 + 1, step):
        for y in range(h - 1, -1, -1):
            if _is_fill(px[x, y]):
                if y > y_bottom:
                    y_bottom = y
                break
    y_top = min(ys)
    span = y_bottom - y_top
    if span < 5 or x1 - x0 < 10:
        return []

    # Échantillonnage régulier des colonnes
    points = []
    width = x1 - x0
    for i in range(samples + 1):
        x = x0 + round(i / samples * width)
        top = None
        for y in range(0, h):
            if _is_fill(px[x, y]):
                top = y
                break
        if top is None:
            continue
        hpct = round((y_bottom - top) / span * 100, 2)
        xpct = round((x - x0) / width * 100, 2)
        points.append([xpct, max(0.0, min(100.0, hpct))])

    return points if len(points) >= 20 else []
