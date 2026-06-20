"""Helpers de parsing PCS partagés."""
import re
from datetime import date, datetime

_ORDINAL_PREFIX = re.compile(r'^\d+(st|nd|rd|th)\s*', re.IGNORECASE)
_CLASS_SUFFIX = re.compile(r'\s*\([^)]*\)\s*$')

GRAND_TOURS = {'tour-de-france', 'giro-d-italia', 'vuelta-a-espana'}
MONUMENTS = {
    'milano-sanremo', 'ronde-van-vlaanderen', 'tour-of-flanders',
    'paris-roubaix', 'liege-bastogne-liege', 'il-lombardia',
}


def clean_name(raw, year=None):
    """Nettoie un nom de course/coureur (retire année, ordinal, suffixe de classe)."""
    if not raw:
        return ''
    name = raw.replace('\xa0', ' ').replace('»', '').replace('»', '').strip()
    if year:
        name = name.replace(str(year), '').strip()
    name = re.sub(r'^\d{4}\s*', '', name).strip()
    name = _ORDINAL_PREFIX.sub('', name)
    name = _CLASS_SUFFIX.sub('', name)
    return name.strip(' -|')


def slug_from_href(href, kind):
    """Extrait le slug d'un href PCS. kind ∈ {race, rider, team, location}."""
    if not href:
        return ''
    href = href.strip().lstrip('/')
    m = re.match(rf'{kind}/([^/]+)', href)
    return m.group(1) if m else ''


def team_slug_year_from_href(href):
    """team/uae-team-emirates-xrg-2026 → ('uae-team-emirates-xrg', 2026)."""
    slug = slug_from_href(href, 'team')
    m = re.search(r'-(\d{4})$', slug)
    if m:
        return slug[: m.start()], int(m.group(1))
    return slug, None


def parse_pcs_date(text, year):
    """'20.01' ou '20.01 - 25.01' → (start_date, end_date)."""
    if not text:
        return None, None
    text = text.replace('\xa0', ' ').strip()
    parts = [p.strip() for p in text.split('-')]

    def one(token):
        m = re.match(r'(\d{1,2})\.(\d{1,2})', token)
        if not m:
            return None
        d, mo = int(m.group(1)), int(m.group(2))
        try:
            return date(year, mo, d)
        except ValueError:
            return None

    start = one(parts[0]) if parts else None
    end = one(parts[1]) if len(parts) > 1 else start
    return start, end


def classification_flags(slug, classification):
    """Déduit (is_stage_race, is_grand_tour, is_monument) d'un slug + classification."""
    is_stage = classification.startswith('2.') if classification else False
    is_gt = slug in GRAND_TOURS
    is_mon = slug in MONUMENTS
    if is_gt:
        is_stage = True
    return is_stage, is_gt, is_mon


def parse_float(text):
    if not text:
        return None
    m = re.search(r'[\d]+(?:[.,]\d+)?', str(text))
    if not m:
        return None
    try:
        return float(m.group().replace(',', '.'))
    except ValueError:
        return None


def parse_int(text):
    if text is None:
        return None
    m = re.search(r'-?\d+', str(text))
    return int(m.group()) if m else None
