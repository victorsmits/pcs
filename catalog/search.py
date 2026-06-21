"""Recherche globale : base locale (instantané) + PCS (exhaustif)."""
from django.db.models import Q

from catalog.models import Rider, Team, Race


def _rider_dict(r):
    sub = (r.current_team.name if r.current_team_id else '') or (r.nationality or '').upper()
    return {'type': 'rider', 'name': r.name, 'url': r.get_absolute_url(), 'subtitle': sub}


def _team_dict(t):
    return {'type': 'team', 'name': t.name, 'url': t.get_absolute_url(),
            'subtitle': f'{t.level or "Équipe"} · {t.year}'}


def _race_dict(r):
    return {'type': 'race', 'name': r.name, 'url': r.get_absolute_url(),
            'subtitle': f'{r.classification or "Course"} · {r.year}'}


def _ranked(model, q, limit):
    """startswith d'abord, puis contains ; dédupliqué, limité."""
    starts = list(model.objects.filter(name__istartswith=q)[:limit])
    ids = [o.pk for o in starts]
    rest = list(model.objects.filter(name__icontains=q).exclude(pk__in=ids)[:limit])
    return (starts + rest)[:limit]


def search_local(q, limit=6):
    riders = _ranked(Rider, q, limit)
    teams = _ranked(Team, q, limit)
    races = _ranked(Race, q, limit)
    return {
        'riders': [_rider_dict(r) for r in riders],
        'teams': [_team_dict(t) for t in teams],
        'races': [_race_dict(r) for r in races],
    }


def search_pcs(q, limit=6):
    """Recherche sur PCS (résultats globaux). Crée les entités stub pour navigation."""
    from core import pcs_client
    from core.parsers.search import parse_search
    from catalog.services import get_or_create_rider, get_or_create_team
    soup = pcs_client.get_soup(f'{pcs_client.PCS_BASE_URL}/search.php?term={q}',
                               cache_ttl=3600)
    if not soup:
        return {'riders': [], 'teams': [], 'races': []}
    parsed = parse_search(soup, limit)
    out = {'riders': [], 'teams': [], 'races': []}
    for r in parsed['riders']:
        rider = get_or_create_rider(r['slug'], r['name'])
        if rider:
            out['riders'].append(_rider_dict(rider))
    for t in parsed['teams']:
        team = get_or_create_team(t['slug'], t['year'], t['name'])
        if team:
            out['teams'].append(_team_dict(team))
    for c in parsed['races']:
        race = Race.objects.filter(slug=c['slug'], year=c['year']).first()
        out['races'].append(_race_dict(race) if race else {
            'type': 'race', 'name': c['name'], 'year': c['year'],
            'url': f"/race/{c['slug']}/{c['year']}/", 'subtitle': f"Course · {c['year']}"})
    return out


def _merge(a, b, limit):
    """Fusionne deux jeux de résultats en dédupliquant par URL."""
    out = {}
    for key in ('riders', 'teams', 'races'):
        seen, merged = set(), []
        for item in a[key] + b[key]:
            if item['url'] in seen:
                continue
            seen.add(item['url'])
            merged.append(item)
        out[key] = merged[:limit]
    return out


def search_all(q, limit=6, include_pcs=True):
    local = search_local(q, limit)
    if not include_pcs:
        return local
    total = sum(len(local[k]) for k in local)
    # On complète avec PCS si le local est maigre (recherche globale)
    if total < limit:
        try:
            return _merge(local, search_pcs(q, limit), limit)
        except Exception:  # noqa: BLE001
            return local
    return local
