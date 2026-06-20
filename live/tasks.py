"""Tâches Celery du moteur live (Phase 0 : squelettes). Implémentées en Phase 3."""
import logging

from celery import shared_task

logger = logging.getLogger('live')


@shared_task
def discover_today():
    """Détecte les étapes du jour et (dés)active les sessions live. (Phase 3)"""
    logger.info('discover_today: à implémenter (Phase 3)')
    return {'created': 0, 'active': 0}


@shared_task
def poll_active_sessions():
    """Ré-enfile le polling pour chaque session live active. (Phase 3)"""
    logger.info('poll_active_sessions: à implémenter (Phase 3)')
    return {'polled': 0}


@shared_task
def poll_live_session(session_id):
    """Poll une session live : fetch page live, extrait `var data`, met à jour la BDD. (Phase 3)"""
    logger.info('poll_live_session(%s): à implémenter (Phase 3)', session_id)
    return {'session_id': session_id}
