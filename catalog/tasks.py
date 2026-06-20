"""Tâches Celery du catalogue."""
import logging

from celery import shared_task
from django.conf import settings

from catalog import services

logger = logging.getLogger('catalog')


@shared_task
def sync_calendar_year(year=None, circuits=None):
    """Synchronise le calendrier d'une année (par défaut la saison courante)."""
    year = year or settings.CURRENT_SEASON
    total = services.sync_calendar(year, circuits)
    return {'year': year, 'races': total}
