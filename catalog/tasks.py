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


@shared_task
def resync_image_profiles(limit=20, window_days=60):
    """Upgrade les profils reconstruits depuis l'image en profils vectoriels
    (cols + altitude) dès que PCS publie les données."""
    return services.resync_image_profiles(limit=limit, window_days=window_days)


@shared_task
def backfill_profile_scales(limit=50):
    """Renseigne l'échelle (min/max altitude) des profils image déjà extraits
    mais sans graduations chiffrées (OCR de l'axe de l'image)."""
    from catalog.models import Stage
    stages = (Stage.objects.filter(profile_from_image=True, min_elevation__isnull=True)
              .exclude(profile_image_url='').order_by('-id')[:limit])
    done = checked = 0
    for stage in stages:
        checked += 1
        try:
            if services.backfill_profile_scale(stage):
                done += 1
        except Exception:  # noqa: BLE001
            continue
    logger.info('Backfill échelles profils : %d/%d renseignés', done, checked)
    return {'checked': checked, 'scaled': done}
