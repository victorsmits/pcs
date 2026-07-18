"""Tâches Celery du moteur live."""
import logging

from celery import shared_task

from django.conf import settings

from core import pcs_circuit
from live import services
from live.models import LiveSession

logger = logging.getLogger('live')


def _disabled_payload(event):
    return {'event': event, 'reason': 'pcs_legacy_disabled'}


@shared_task
def discover_today():
    """Legacy PCS discovery is disabled unless explicitly enabled."""
    if not getattr(settings, 'PCS_LEGACY_ENABLED', False):
        logger.info('Découverte PCS legacy désactivée', extra=_disabled_payload('pcs_discover_disabled'))
        return {'task_success': True, 'queued': 0, 'reason': 'pcs_legacy_disabled'}
    result = services.discover_live_today()
    return {'task_success': True, **result}


@shared_task
def poll_active_sessions():
    """Enfile un poll legacy uniquement si le kill switch PCS est activé."""
    if not getattr(settings, 'PCS_LEGACY_ENABLED', False):
        logger.info('Polling PCS legacy désactivé', extra=_disabled_payload('pcs_polling_disabled'))
        return {'task_success': True, 'queued': 0, 'reason': 'pcs_legacy_disabled'}

    state = pcs_circuit.current_state()
    if state.open:
        logger.warning('PCS polling skipped', extra={'event': 'pcs_polling_skipped', 'retry_after': state.retry_after})
        return {'task_success': True, 'queued': 0, 'reason': 'pcs_circuit_open', 'retry_after': state.retry_after}

    ids = list(LiveSession.objects.filter(is_active=True).values_list('id', flat=True))
    for sid in ids:
        poll_live_session.delay(sid)
    logger.info('Sessions live remises en file', extra={'event': 'task_success', 'queued': len(ids)})
    return {'task_success': True, 'queued': len(ids)}


@shared_task
def poll_live_session(session_id):
    """Poll legacy d'une session, désactivé par défaut."""
    if not getattr(settings, 'PCS_LEGACY_ENABLED', False):
        logger.info(
            'Poll session PCS legacy désactivé',
            extra={**_disabled_payload('pcs_poll_session_disabled'), 'session_id': session_id},
        )
        return {'task_success': True, 'session_id': session_id, 'ok': False, 'reason': 'pcs_legacy_disabled'}

    session = LiveSession.objects.select_related('stage__race').filter(id=session_id).first()
    if not session:
        return {'task_success': True, 'functional_failure': True, 'error': 'session introuvable'}
    result = services.sync_live_session(session.stage, force=True)
    ok = bool(result)
    logger.info('Poll session terminé', extra={'event': 'task_success' if ok else 'functional_failure', 'session_id': session_id})
    return {'task_success': True, 'session_id': session_id, 'ok': ok, 'functional_failure': not ok}
