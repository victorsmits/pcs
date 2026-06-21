"""Tâches Celery du moteur live."""
import logging

from celery import shared_task

from live import services
from live.models import LiveSession

logger = logging.getLogger('live')


@shared_task
def discover_today():
    """Détecte les étapes live du jour et (dés)active les sessions."""
    return services.discover_live_today()


@shared_task
def poll_active_sessions():
    """Enfile un poll pour chaque session live active."""
    ids = list(LiveSession.objects.filter(is_active=True).values_list('id', flat=True))
    for sid in ids:
        poll_live_session.delay(sid)
    return {'queued': len(ids)}


@shared_task
def poll_live_session(session_id):
    """Poll une session live : fetch page live, extrait `var data`, met à jour la BDD."""
    session = LiveSession.objects.select_related('stage__race').filter(id=session_id).first()
    if not session:
        return {'error': 'session introuvable'}
    result = services.sync_live_session(session.stage, force=True)
    return {'session_id': session_id, 'ok': bool(result)}
