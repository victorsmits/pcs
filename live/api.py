"""API JSON live (polling front)."""
from datetime import date, timedelta

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from catalog.models import Stage
from live.models import LiveSession
from live import services

STALE_AFTER = timedelta(seconds=20)


def _maybe_refresh(session):
    """En dev (ou si le worker ne tourne pas), rafraîchit si la session est active et périmée."""
    if not session or not session.is_active:
        return session
    stale = (session.last_polled_at is None) or (timezone.now() - session.last_polled_at > STALE_AFTER)
    if stale:
        try:
            services.sync_live_session(session.stage, force=True)
            session.refresh_from_db()
        except Exception:  # noqa: BLE001
            pass
    return session


def _upcoming_keypoints(session):
    """Points clés (cols/sprints) encore à venir, avec distance restante."""
    data = session.raw_data or {}
    km_done = session.km_done or 0
    out = []
    for kp in data.get('keypoints', []) or []:
        km = kp.get('km')
        if km is None:
            continue
        to_go = round(km - km_done, 1)
        if to_go < -1:
            continue  # déjà passé
        out.append({
            'name': kp.get('title', ''),
            'km': km,
            'to_go': to_go,
            'category': str(kp.get('category') or ''),
            'length': kp.get('lengte') or None,
            'avg_grad': kp.get('avg_perc') or None,
            'passed': to_go < 0,
        })
    out.sort(key=lambda k: k['km'])
    return out[:8]


def _serialize(session):
    return {
        'available': True,
        'race_status': session.race_status,
        'is_active': session.is_active,
        'finished': session.finished,
        'km_done': session.km_done,
        'km_to_go': session.km_to_go,
        'max_km': session.max_km,
        'perc': session.perc,
        'avg_speed': round(session.avg_speed, 1) if session.avg_speed else 0,
        'groups': [
            {'label': g.label, 'gap': g.gap, 'rider_count': g.rider_count,
             'profile_pct': g.profile_pct, 'riders': g.riders}
            for g in session.groups.all()
        ],
        'events': [
            {'seqnr': e.seqnr, 'marker': e.marker, 'text': e.text}
            for e in session.events.all()[:40]
        ],
        'keypoints': _upcoming_keypoints(session),
        'updated_at': session.last_polled_at.isoformat() if session.last_polled_at else None,
    }


def stage_live_data(request, slug, year, number):
    stage = get_object_or_404(Stage, race__slug=slug, race__year=year, number=number)
    session = LiveSession.objects.filter(stage=stage).first()
    if not session:
        return JsonResponse({'available': False}, status=404)
    _maybe_refresh(session)
    return JsonResponse(_serialize(session))


def today_live(request):
    sessions = (LiveSession.objects.filter(is_active=True)
                .select_related('stage__race').order_by('-updated_at'))
    return JsonResponse({'sessions': [
        {
            'race': s.stage.race.name, 'slug': s.stage.race.slug, 'year': s.stage.race.year,
            'stage': s.stage.number, 'race_status': s.race_status,
            'perc': s.perc, 'km_to_go': s.km_to_go,
        } for s in sessions
    ]})
