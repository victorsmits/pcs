"""Tâches Celery du moteur live."""
import logging

from celery import shared_task

from core import pcs_circuit, pcs_client
from live import services
from live.models import LiveSession

logger = logging.getLogger('live')


def _circuit_payload(event):
    state = pcs_circuit.current_state()
    return {
        'event': event,
        'consecutive_failures': state.failure_count,
        'circuit_state': 'open' if state.open else 'closed',
        'retry_after': state.retry_after,
    }


@shared_task
def discover_today():
    """Détecte les étapes live du jour et (dés)active les sessions."""
    state = pcs_circuit.current_state()
    if state.open:
        logger.warning('Découverte PCS ignorée: circuit ouvert', extra=_circuit_payload('pcs_discover_skipped'))
        return {'task_success': True, 'queued': 0, 'reason': 'pcs_circuit_open', 'retry_after': state.retry_after}
    try:
        result = services.discover_live_today()
        return {'task_success': True, **result}
    except pcs_client.PCSAccessForbiddenError as exc:
        logger.warning(
            'Découverte PCS bloquée par HTTP 403',
            extra={**_circuit_payload('remote_access_blocked'), 'url': exc.url, 'status_code': 403},
        )
        return {'task_success': True, 'functional_failure': True,
                'remote_access_blocked': True, 'retry_after': exc.retry_after}
    except pcs_client.PCSCircuitOpenError as exc:
        logger.warning('Découverte PCS ignorée: circuit ouvert', extra=_circuit_payload('pcs_discover_skipped'))
        return {'task_success': True, 'reason': 'pcs_circuit_open', 'retry_after': exc.retry_after}
    except Exception:
        logger.exception('Échec temporaire de la découverte PCS', extra=_circuit_payload('temporary_network_failure'))
        return {'task_success': True, 'functional_failure': True, 'temporary_network_failure': True}


@shared_task
def poll_active_sessions():
    """Enfile un poll pour chaque session live active."""
    state = pcs_circuit.current_state()
    if state.open:
        logger.warning('PCS polling skipped', extra=_circuit_payload('pcs_polling_skipped'))
        return {'task_success': True, 'queued': 0, 'reason': 'pcs_circuit_open', 'retry_after': state.retry_after}

    ids = list(LiveSession.objects.filter(is_active=True).values_list('id', flat=True))
    for sid in ids:
        poll_live_session.delay(sid)
    logger.info('Sessions live remises en file', extra={**_circuit_payload('task_success'), 'queued': len(ids)})
    return {'task_success': True, 'queued': len(ids)}


@shared_task
def poll_live_session(session_id):
    """Poll une session live : fetch page live, extrait `var data`, met à jour la BDD."""
    state = pcs_circuit.current_state()
    if state.open:
        logger.warning(
            'Poll session ignoré: circuit PCS ouvert',
            extra={**_circuit_payload('pcs_poll_session_skipped'), 'session_id': session_id},
        )
        return {'task_success': True, 'session_id': session_id, 'ok': False,
                'reason': 'pcs_circuit_open', 'retry_after': state.retry_after}

    session = LiveSession.objects.select_related('stage__race').filter(id=session_id).first()
    if not session:
        return {'task_success': True, 'functional_failure': True, 'error': 'session introuvable'}
    try:
        result = services.sync_live_session(session.stage, force=True)
    except pcs_client.PCSAccessForbiddenError as exc:
        logger.warning(
            'Poll session bloqué par HTTP 403 PCS',
            extra={**_circuit_payload('remote_access_blocked'),
                   'url': exc.url, 'status_code': 403, 'session_id': session_id},
        )
        return {'task_success': True, 'session_id': session_id, 'ok': False,
                'functional_failure': True, 'remote_access_blocked': True,
                'retry_after': exc.retry_after}
    except pcs_client.PCSCircuitOpenError as exc:
        logger.warning(
            'Poll session ignoré: circuit PCS ouvert',
            extra={**_circuit_payload('pcs_poll_session_skipped'), 'session_id': session_id},
        )
        return {'task_success': True, 'session_id': session_id, 'ok': False,
                'reason': 'pcs_circuit_open', 'retry_after': exc.retry_after}
    except Exception:
        logger.exception(
            'Échec temporaire du poll live',
            extra={**_circuit_payload('temporary_network_failure'), 'session_id': session_id},
        )
        return {'task_success': True, 'session_id': session_id, 'ok': False,
                'functional_failure': True, 'temporary_network_failure': True}

    ok = bool(result)
    logger.info(
        'Poll session terminé',
        extra={**_circuit_payload('task_success' if ok else 'functional_failure'), 'session_id': session_id},
    )
    return {'task_success': True, 'session_id': session_id, 'ok': ok,
            'functional_failure': not ok}
