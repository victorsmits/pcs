"""API JSON live (polling front) + abonnements push."""
import json
from datetime import date, timedelta

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from catalog.models import Race, Stage
from live.models import LiveSession, PushSubscription, RaceFollow
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
        if kp.get('type') in (6, 9):  # villes / frontières
            continue
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
    return out[:15]


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
        'start_time': session.start_time,
        'groups': [
            {'label': g.label, 'gap': g.gap, 'rider_count': g.rider_count,
             'profile_pct': g.profile_pct, 'riders': g.riders}
            for g in session.groups.all()
        ],
        'events': [
            {'seqnr': e.seqnr, 'marker': e.marker, 'text': e.text, 'html': e.html}
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


# ─────────────────────────── Notifications push ───────────────────────────

def push_config(request):
    """Expose l'état du push + la clé publique VAPID (applicationServerKey)."""
    return JsonResponse({
        'enabled': bool(getattr(settings, 'PUSH_ENABLED', False)),
        'public_key': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
    })


def _subscription_from_payload(sub):
    """Upsert d'un PushSubscription depuis le dict d'abonnement du navigateur."""
    endpoint = (sub or {}).get('endpoint')
    keys = (sub or {}).get('keys') or {}
    p256dh, auth = keys.get('p256dh'), keys.get('auth')
    if not (endpoint and p256dh and auth):
        return None
    obj, _ = PushSubscription.objects.update_or_create(
        endpoint=endpoint, defaults={'p256dh': p256dh, 'auth': auth})
    return obj


@csrf_exempt
@require_POST
def push_subscribe(request):
    """Enregistre (ou rafraîchit) l'abonnement push de l'appareil."""
    try:
        body = json.loads(request.body or '{}')
    except ValueError:
        return JsonResponse({'error': 'json invalide'}, status=400)
    obj = _subscription_from_payload(body.get('subscription'))
    if not obj:
        return JsonResponse({'error': 'abonnement incomplet'}, status=400)
    ua = request.META.get('HTTP_USER_AGENT', '')[:300]
    if ua and obj.user_agent != ua:
        obj.user_agent = ua
        obj.save(update_fields=['user_agent'])
    return JsonResponse({'ok': True})


@csrf_exempt
@require_POST
def push_follow(request):
    """Active/désactive le suivi d'une course pour un abonnement (toggle)."""
    try:
        body = json.loads(request.body or '{}')
    except ValueError:
        return JsonResponse({'error': 'json invalide'}, status=400)

    sub = _subscription_from_payload(body.get('subscription'))
    if not sub:
        endpoint = body.get('endpoint')
        sub = PushSubscription.objects.filter(endpoint=endpoint).first() if endpoint else None
    if not sub:
        return JsonResponse({'error': 'abonnement inconnu'}, status=400)

    race = Race.objects.filter(slug=body.get('slug'), year=body.get('year')).first()
    if not race:
        return JsonResponse({'error': 'course inconnue'}, status=404)

    follow = bool(body.get('follow', True))
    if follow:
        RaceFollow.objects.get_or_create(subscription=sub, race=race)
    else:
        RaceFollow.objects.filter(subscription=sub, race=race).delete()
    return JsonResponse({'following': follow})


def push_following(request):
    """Indique si l'appareil (endpoint) suit déjà la course donnée."""
    endpoint = request.GET.get('endpoint', '')
    race = Race.objects.filter(slug=request.GET.get('slug'),
                               year=request.GET.get('year')).first()
    following = bool(endpoint and race and RaceFollow.objects.filter(
        subscription__endpoint=endpoint, race=race).exists())
    return JsonResponse({
        'following': following,
        'enabled': bool(getattr(settings, 'PUSH_ENABLED', False)),
    })
