"""Services de synchronisation du catalogue depuis PCS."""
import logging
import time

from django.utils import timezone

from core import pcs_client
from core.models import SyncLog
from core.parsers.calendar import parse_calendar
from core.parsers.stage import parse_stage_info, parse_stage_list, parse_stage_images, parse_stage_winners
from core.parsers.profile import extract_elevation_points
from core.parsers.live import parse_live_data, keypoints_from_data
from catalog.models import Race, Stage, Climb, Rider, Category, StageType

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


def sync_race_detail(race, force=False):
    """Récupère la page course et crée/maj les étapes (course par étapes)."""
    if race.detail_synced_at and not force:
        return race

    t0 = time.monotonic()
    url = f'{pcs_client.PCS_BASE_URL}/race/{race.slug}/{race.year}'
    soup = pcs_client.get_soup(url, cache_ttl=1800, force=force)
    if not soup:
        _log('race', f'{race.slug}/{race.year}', SyncLog.Status.ERROR, 'fetch échoué')
        return race

    stages = parse_stage_list(soup, race.year)
    winners = parse_stage_winners(soup)
    for s in stages:
        defaults = {'departure': s['departure'][:120], 'arrival': s['arrival'][:120]}
        if s.get('date'):
            defaults['date'] = s['date']
        if s.get('distance'):
            defaults['distance'] = s['distance']
        w = winners.get(s['number'])
        if w:
            defaults['winner'] = get_or_create_rider(w['slug'], w['name'])
        Stage.objects.update_or_create(race=race, number=s['number'], defaults=defaults)

    if stages and not race.is_stage_race:
        race.is_stage_race = True

    race.detail_synced_at = timezone.now()
    race.save(update_fields=['is_stage_race', 'detail_synced_at'])
    _log('race', f'{race.slug}/{race.year}', SyncLog.Status.OK,
         f'{len(stages)} étapes, {len(winners)} vainqueurs', int((time.monotonic() - t0) * 1000))
    return race


def sync_stage_detail(stage, force=False):
    """Récupère infos + image profil (page étape) et points d'altitude (page live)."""
    if stage.detail_synced_at and not force:
        return stage

    t0 = time.monotonic()
    base = f'{pcs_client.PCS_BASE_URL}/race/{stage.race.slug}/{stage.race.year}/stage-{stage.number}'

    soup = pcs_client.get_soup(base, cache_ttl=1800, force=force)
    if soup:
        info = parse_stage_info(soup)
        for field, value in info.items():
            if value not in (None, ''):
                setattr(stage, field, value)

    # Images (profil HD, carte/tracé, profil d'arrivée) depuis /info/profiles
    img_soup = pcs_client.get_soup(base + '/info/profiles', cache_ttl=86400, force=force)
    if img_soup:
        for field, value in parse_stage_images(img_soup).items():
            if value:
                setattr(stage, field, value)

    # Profil d'altitude + altitudes min/max depuis la page live (polygone clip-path)
    live_html = pcs_client.fetch_text(base + '/live', cache_ttl=1800, force=force)
    if live_html:
        points = extract_elevation_points(live_html)
        if points:
            stage.elevation_points = points
        ldata = parse_live_data(live_html)
        if ldata:
            if ldata.get('min_ele') is not None:
                stage.min_elevation = int(ldata['min_ele'])
            if ldata.get('max_ele') is not None:
                stage.max_elevation = int(ldata['max_ele'])
            if not stage.distance and ldata.get('maxkm'):
                stage.distance = ldata['maxkm']
            # Cols / points clés
            keypoints = keypoints_from_data(ldata)
            if keypoints:
                stage.climbs.all().delete()
                for kp in keypoints:
                    Climb.objects.create(
                        stage=stage, name=kp['name'][:160], km=kp['km'],
                        length=kp['length'], avg_grad=kp['avg_grad'],
                        category=str(kp['category'])[:10],
                        kind=Climb.Kind.CLIMB if kp['category'] else Climb.Kind.SPRINT,
                        location_url=kp['url'][:200],
                    )

    stage.detail_synced_at = timezone.now()
    stage.save()
    _log('stage', f'{stage.race.slug}/{stage.race.year}/{stage.number}', SyncLog.Status.OK,
         f'{len(stage.elevation_points)} pts profil', int((time.monotonic() - t0) * 1000))
    return stage
