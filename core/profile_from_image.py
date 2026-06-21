"""Extraction de la silhouette d'altitude depuis une image de profil PCS.

Les profils PCS sont des images où l'aire sous la courbe d'altitude est remplie
en vert sur fond blanc. On scanne chaque colonne pour trouver le sommet du vert
→ points d'altitude relatifs [[x%, h%]], comme le polygone des pages live.

En complément, `estimate_elevation_range` lit les libellés de l'axe vertical
(0 / 200 / 400 …) par OCR pour caler la silhouette en mètres réels (échelle).
L'OCR est optionnel : sans Tesseract, on renvoie (None, None) et le profil
s'affiche sans graduations chiffrées (comportement historique).
"""
import io
import logging

logger = logging.getLogger('core')


def _is_fill(p):
    """Pixel appartenant à la silhouette (vert PCS, clair ou foncé)."""
    r, g, b = p[0], p[1], p[2]
    return g > 110 and g >= r - 10 and g > b + 25


def _silhouette_geometry(px, w, h):
    """Renvoie (x0, x1, y_top, y_bottom) de l'aire verte, ou None.

    y_top = sommet (altitude max), y_bottom = base (altitude min) de la silhouette.
    """
    step = max(1, w // 400)
    xs, ys = [], []
    for x in range(0, w, step):
        for y in range(0, h, max(1, h // 200)):
            if _is_fill(px[x, y]):
                xs.append(x)
                ys.append(y)
                break
    if len(xs) < 20:
        return None
    x0, x1 = min(xs), max(xs)
    y_bottom = 0
    for x in range(x0, x1 + 1, step):
        for y in range(h - 1, -1, -1):
            if _is_fill(px[x, y]):
                if y > y_bottom:
                    y_bottom = y
                break
    y_top = min(ys)
    if y_bottom - y_top < 5 or x1 - x0 < 10:
        return None
    return x0, x1, y_top, y_bottom


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

    geo = _silhouette_geometry(px, w, h)
    if not geo:
        return []
    x0, x1, y_top, y_bottom = geo
    span = y_bottom - y_top

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


def _ocr_axis_labels(im, x_right):
    """OCR des nombres de l'axe vertical (zone à gauche de x_right).

    Renvoie [(y_centre_px, valeur_m), …] trié par y, ou [] si OCR indisponible.
    """
    try:
        import pytesseract
    except ImportError:
        return []
    # Bande de gauche, agrandie ×4 pour fiabiliser l'OCR des petits libellés.
    strip = im.crop((0, 0, max(8, x_right), im.size[1]))
    scale = 4
    big = strip.resize((strip.size[0] * scale, strip.size[1] * scale))
    cfg = '--psm 11 -c tessedit_char_whitelist=0123456789'
    try:
        data = pytesseract.image_to_data(
            big, config=cfg, output_type=pytesseract.Output.DICT)
    except Exception:  # noqa: BLE001 — Tesseract absent / illisible
        return []
    out = []
    for txt, top, ht, conf in zip(data['text'], data['top'], data['height'], data['conf']):
        t = (txt or '').strip()
        if not t.isdigit():
            continue
        try:
            if float(conf) < 30:
                continue
        except (TypeError, ValueError):
            pass
        y_center = (top + ht / 2) / scale  # retour aux coords d'origine
        out.append((round(y_center, 1), int(t)))
    out.sort(key=lambda a: a[0])
    return out


def _linear_fit(pairs):
    """Régression meters = a*y + b sur [(y, m), …]. Renvoie (a, b) ou None."""
    n = len(pairs)
    if n < 2:
        return None
    sy = sum(p[0] for p in pairs)
    sm = sum(p[1] for p in pairs)
    syy = sum(p[0] * p[0] for p in pairs)
    sym = sum(p[0] * p[1] for p in pairs)
    denom = n * syy - sy * sy
    if denom == 0:
        return None
    a = (n * sym - sy * sm) / denom
    b = (sm - a * sy) / n
    return a, b


def estimate_elevation_range(image_bytes):
    """Estime (min_ele, max_ele) en mètres pour la silhouette, via OCR de l'axe.

    Renvoie (None, None) si l'image, l'OCR ou les contrôles de cohérence échouent
    (dégradation propre : le profil s'affiche alors sans échelle chiffrée).
    """
    try:
        from PIL import Image
    except ImportError:
        return None, None
    try:
        im = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    except Exception:  # noqa: BLE001
        return None, None

    w, h = im.size
    if w < 50 or h < 30:
        return None, None
    px = im.load()
    geo = _silhouette_geometry(px, w, h)
    if not geo:
        return None, None
    x0, _x1, y_top, y_bottom = geo

    labels = _ocr_axis_labels(im, x0)
    # Dédoublonne par valeur (garde le 1er y), exige ≥2 repères distincts.
    seen, pairs = set(), []
    for y, val in labels:
        if val in seen:
            continue
        seen.add(val)
        pairs.append((y, val))
    if len(pairs) < 2:
        return None, None

    fit = _linear_fit(pairs)
    if not fit:
        return None, None
    a, b = fit
    if a >= 0:  # l'altitude doit croître vers le haut (y décroissant)
        return None, None

    # Contrôle de cohérence : les repères doivent coller à la droite (résidus faibles).
    span_m = max(v for _, v in pairs) - min(v for _, v in pairs)
    if span_m <= 0:
        return None, None
    for y, val in pairs:
        if abs((a * y + b) - val) > max(15, 0.1 * span_m):
            return None, None

    min_ele = a * y_bottom + b
    max_ele = a * y_top + b
    if max_ele <= min_ele:
        return None, None
    min_ele = max(0, round(min_ele / 5) * 5)
    max_ele = round(max_ele / 5) * 5
    if not (0 <= min_ele < max_ele <= 6000) or (max_ele - min_ele) < 10:
        return None, None
    return int(min_ele), int(max_ele)
