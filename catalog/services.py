"""Services de synchronisation du catalogue depuis PCS."""
import logging
import time

from django.utils import timezone

from core import pcs_client
from core.models import SyncLog
from core.parsers.calendar import parse_calendar
from catalog.models import Race, Rider, Category

logger = logging.getLogger('catalog')

# Circuits PCS pour races.php (id, libellé, catégorie par défaut)
CIRCUITS = {
    'wt': ('1', 'UCI WorldTour', Category.ME),
    'pro': ('26', 'UCI ProSeries', Category.ME),
    'wwt': ('24', "UCI Women's WorldTour", Category.WE),
    'we': ('16', 'Women Elite', Category.WE),
    'wc': ('2', 'UCI World Championships', Category.ME),
    'europe': ('13', 'UCI Europe Tour', Category.ME),
    'asia': ('12', 'UCI Asia Tour', Category.ME),
    'america': ('18', 'UCI America Tour', Category.ME),
    'africa': ('11', 'UCI Africa Tour', Category.ME),
    'oceania': ('14', 'UCI Oceania Tour', Category.ME),
    'nc': ('23', 'National Championships', Category.ME),
}
# Périmètre par défaut : grandes courses H/F. 'all' = tous les circuits ci-dessus.
DEFAULT_CIRCUITS = ['wt', 'pro', 'wwt', 'we']


def _log(entity_type, ref, status, message='', duration_ms=None):
    SyncLog.objects.create(
        entity_type=entity_type, ref=ref, status=status,
        message=message[:2000], duration_ms=duration_ms,
    )


def get_or_create_rider(slug, name='', nationality=''):
    """Récupère ou crée un coureur (stub) par slug."""
    if not slug:
        return None
    rider, created = Rider.objects.get_or_create(
        slug=slug, defaults={'name': name or slug.replace('-', ' ').title(), 'nationality': nationality},
    )
    if not created and name and rider.name != name and rider.name == slug.replace('-', ' ').title():
        rider.name = name
        rider.save(update_fields=['name'])
    return rider


def sync_calendar(year, circuits=None):
    """Synchronise le calendrier PCS pour une année et une liste de circuits.

    Renvoie le nombre de courses créées/mises à jour.
    """
    circuits = circuits or DEFAULT_CIRCUITS
    if circuits == ['all']:
        circuits = list(CIRCUITS.keys())
    total = 0
    for key in circuits:
        if key not in CIRCUITS:
            continue
        circuit_id, circuit_name, category = CIRCUITS[key]
        url = (f'{pcs_client.PCS_BASE_URL}/races.php?year={year}'
               f'&circuit={circuit_id}&class=&filter=Filter')
        t0 = time.monotonic()
        soup = pcs_client.get_soup(url, cache_ttl=3600, referer=f'{pcs_client.PCS_BASE_URL}/races.php')
        if not soup:
            _log('calendar', f'{year}/{key}', SyncLog.Status.ERROR, 'fetch échoué')
            continue

        races = parse_calendar(soup, year)
        saved = 0
        for data in races:
            winner = get_or_create_rider(data.pop('winner_slug', ''), data.pop('winner_name', ''))
            Race.objects.update_or_create(
                slug=data['slug'], year=data['year'],
                defaults={
                    'name': data['name'],
                    'classification': data['classification'][:10],
                    'category': category,
                    'circuit': circuit_name,
                    'start_date': data['start_date'],
                    'end_date': data['end_date'],
                    'is_stage_race': data['is_stage_race'],
                    'is_grand_tour': data['is_grand_tour'],
                    'is_monument': data['is_monument'],
                    'winner': winner,
                },
            )
            saved += 1
        total += saved
        dt = int((time.monotonic() - t0) * 1000)
        _log('calendar', f'{year}/{key}', SyncLog.Status.OK if saved else SyncLog.Status.EMPTY,
             f'{saved} courses', dt)
        logger.info('Calendrier %s/%s : %s courses', year, key, saved)

    return total
