"""Recherche locale provider-agnostic. Aucun accès fournisseur depuis le web."""

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


def search_all(q, limit=6, include_pcs=False):
    return search_local(q, limit)
