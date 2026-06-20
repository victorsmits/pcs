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
from core.parsers.results import parse_results_table, find_standings_table
from core.parsers.rider import parse_rider
from core.parsers.team import parse_team
from catalog.models import (
    Race, Stage, Climb, Rider, Team, Membership, Result, Category, StageType, ClassificationType,
)

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
    updates = []
    # Rafraîchit un nom « stub » (sans espace, ou dérivé du slug) avec un meilleur nom
    if name and name != rider.name and (' ' not in rider.name or rider.name == slug.replace('-', ' ').title()):
        rider.name = name
        updates.append('name')
    if nationality and not rider.nationality:
        rider.nationality = nationality
        updates.append('nationality')
    if updates:
        rider.save(update_fields=updates)
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


def get_or_create_team(slug, year, name=''):
    if not slug:
        return None
    year = year or 0
    team = (Team.objects.filter(slug=slug, year=year).first()
            or Team.objects.filter(slug=slug).order_by('-year').first())
    if team:
        return team
    return Team.objects.create(slug=slug, year=year or None,
                               name=name or slug.replace('-', ' ').title())


def _save_results(race, rows, classification, stage=None):
    """Upsert d'une liste de résultats parsés pour un classement donné."""
    saved = 0
    for r in rows:
        rider = get_or_create_rider(r['rider_slug'], r['rider_name'], r.get('nat', ''))
        if not rider:
            continue
        team = get_or_create_team(r['team_slug'], r['team_year'], r['team_name'])
        Result.objects.update_or_create(
            race=race, stage=stage, rider=rider, classification=classification,
            defaults={
                'team': team, 'rank': r['rank'],
                'time_gap': (r['time_gap'] or r['time'])[:30],
                'points_uci': r['points_uci'], 'points_pcs': r['points_pcs'],
                'status': r['status'],
            },
        )
        saved += 1
    return saved


def sync_stage_results(stage, force=True):
    """Récupère et stocke les résultats d'une étape (classement d'étape)."""
    t0 = time.monotonic()
    url = f'{pcs_client.PCS_BASE_URL}/race/{stage.race.slug}/{stage.race.year}/stage-{stage.number}'
    soup = pcs_client.get_soup(url, cache_ttl=120, force=force)
    if not soup:
        return 0
    rows = parse_results_table(soup)
    saved = _save_results(stage.race, rows, ClassificationType.STAGE, stage=stage)
    # Vainqueur d'étape
    winner_row = next((x for x in rows if x['rank'] == 1), None)
    if winner_row:
        w = get_or_create_rider(winner_row['rider_slug'], winner_row['rider_name'])
        Stage.objects.filter(pk=stage.pk).update(winner=w)
    _log('results', f'{stage.race.slug}/{stage.race.year}/{stage.number}',
         SyncLog.Status.OK if saved else SyncLog.Status.EMPTY,
         f'{saved} résultats', int((time.monotonic() - t0) * 1000))
    return saved


def sync_gc(race, force=False):
    """Classement général. GC officiel si dispo (édition terminée), sinon GC
    provisoire dérivé de la colonne « GC » de la dernière étape disputée."""
    t0 = time.monotonic()
    url = f'{pcs_client.PCS_BASE_URL}/race/{race.slug}/{race.year}/gc'
    soup = pcs_client.get_soup(url, cache_ttl=300, force=force)
    rows = parse_results_table(find_standings_table(soup)) if soup else []

    if rows:  # GC officiel (server-side)
        saved = _save_results(race, rows, ClassificationType.GC)
        leader = next((x for x in rows if x['rank'] == 1), None)
        if leader:
            race.winner = get_or_create_rider(leader['rider_slug'], leader['rider_name'])
            race.save(update_fields=['winner'])
        _log('results', f'{race.slug}/{race.year}/gc', SyncLog.Status.OK, f'{saved} au GC',
             int((time.monotonic() - t0) * 1000))
        return saved

    # --- GC provisoire (course en cours) ---
    return _sync_provisional_gc(race, t0)


def _sync_provisional_gc(race, t0=None):
    """Construit un GC provisoire à partir de la colonne GC de la dernière étape."""
    from datetime import date as _date
    t0 = t0 or time.monotonic()
    # On parcourt les étapes disputées de la plus récente à la plus ancienne
    # jusqu'à en trouver une dont les résultats portent une colonne GC.
    candidates = list(race.stages.filter(date__lte=_date.today()).order_by('-number'))
    if not candidates:
        candidates = list(race.stages.order_by('-number'))
    rows = []
    used = None
    for st in candidates:
        url = f'{pcs_client.PCS_BASE_URL}/race/{race.slug}/{race.year}/stage-{st.number}'
        soup = pcs_client.get_soup(url, cache_ttl=120)
        if not soup:
            continue
        gc_rows = [r for r in parse_results_table(soup) if r.get('gc_rank')]
        if gc_rows:
            rows, used = gc_rows, st
            break
    if not rows:
        return 0
    rows.sort(key=lambda r: r['gc_rank'])
    latest = used
    Result.objects.filter(race=race, classification=ClassificationType.GC).delete()
    saved = 0
    for r in rows[:60]:
        rider = get_or_create_rider(r['rider_slug'], r['rider_name'], r.get('nat', ''))
        if not rider:
            continue
        team = get_or_create_team(r['team_slug'], r['team_year'], r['team_name'])
        Result.objects.update_or_create(
            race=race, stage=None, rider=rider, classification=ClassificationType.GC,
            defaults={'team': team, 'rank': r['gc_rank'], 'time_gap': '', 'status': r['status']},
        )
        saved += 1
    _log('results', f'{race.slug}/{race.year}/gc', SyncLog.Status.OK,
         f'GC provisoire {saved} (étape {latest.number})', int((time.monotonic() - t0) * 1000))
    return saved


def sync_rider(rider, force=False):
    """Récupère la page coureur : met à jour le modèle, renvoie le dict parsé (avec top_results)."""
    url = f'{pcs_client.PCS_BASE_URL}/rider/{rider.slug}'
    soup = pcs_client.get_soup(url, cache_ttl=86400, force=force)
    if not soup:
        return None
    data = parse_rider(soup)
    fields = []
    for attr in ('birthdate', 'weight', 'height', 'photo_url'):
        if data.get(attr) and getattr(rider, attr) != data[attr]:
            setattr(rider, attr, data[attr]); fields.append(attr)
    if data.get('nationality') and not rider.nationality:
        rider.nationality = data['nationality']; fields.append('nationality')
    if data.get('specialties'):
        rider.specialties = data['specialties']; fields.append('specialties')
    if data.get('team_slug'):
        team = get_or_create_team(data['team_slug'], None, data.get('team_name', ''))
        if team and rider.current_team_id != team.id:
            rider.current_team = team; fields.append('current_team')
    rider.detail_synced_at = timezone.now(); fields.append('detail_synced_at')
    rider.save(update_fields=fields)
    _log('rider', rider.slug, SyncLog.Status.OK, f'{len(data["top_results"])} résultats')
    return data


def sync_team(team, force=False):
    """Récupère la page équipe : met à jour le modèle + effectif (Membership)."""
    url = f'{pcs_client.PCS_BASE_URL}/team/{team.slug}-{team.year}'
    soup = pcs_client.get_soup(url, cache_ttl=86400, force=force)
    if not soup:
        return None
    data = parse_team(soup)
    if data.get('level') and not team.level:
        team.level = data['level']
    if data.get('nationality') and not team.nationality:
        team.nationality = data['nationality']
    team.detail_synced_at = timezone.now()
    team.save()
    roster = []
    for r in data['roster']:
        rider = get_or_create_rider(r['slug'], r['name'])
        if rider:
            Membership.objects.update_or_create(team=team, rider=rider, year=team.year)
            roster.append(rider)
    _log('team', f'{team.slug}/{team.year}', SyncLog.Status.OK, f'{len(roster)} coureurs')
    return data


def get_past_editions(race, n=6):
    """Éditions précédentes (même slug) avec leur vainqueur — backfill paresseux.

    Renvoie [{'year', 'race', 'winner'}] des n années précédentes.
    """
    editions = []
    for year in range(race.year - 1, race.year - 1 - n, -1):
        edition = Race.objects.filter(slug=race.slug, year=year).first()
        if not edition:
            edition = Race.objects.create(
                slug=race.slug, year=year, name=race.name,
                classification=race.classification, category=race.category,
                circuit=race.circuit, is_stage_race=race.is_stage_race,
                is_grand_tour=race.is_grand_tour, is_monument=race.is_monument,
            )
        if not edition.winner:
            try:
                if edition.is_stage_race:
                    sync_gc(edition)
                else:
                    sync_oneday_result(edition)
                edition.refresh_from_db()
            except Exception:  # noqa: BLE001
                pass
        if edition.winner:
            editions.append({'year': year, 'race': edition, 'winner': edition.winner})
    return editions


# Ordre conventionnel des maillots PCS (label, couleur CSS)
JERSEY_LABELS = [
    ('Leader', 'amber'),
    ('Points', 'green'),
    ('Montagne', 'red'),
    ('Jeunes', 'white'),
    ('Combatif', 'blue'),
]


def sync_pcs_ranking(year, gender='me', force=False):
    """Synchronise le classement PCS individuel (me=hommes, we=femmes)."""
    from core.parsers.ranking import parse_pcs_ranking
    from catalog.models import Ranking
    url = f'{pcs_client.PCS_BASE_URL}/rankings/{gender}/individual'
    soup = pcs_client.get_soup(url, cache_ttl=6 * 3600, force=force)
    if not soup:
        return 0
    rows = parse_pcs_ranking(soup)
    saved = 0
    for r in rows:
        rider = get_or_create_rider(r['rider_slug'], r['rider_name'])
        if not rider:
            continue
        if r['team_slug'] and not rider.current_team_id:
            rider.current_team = get_or_create_team(r['team_slug'], r['team_year'], r['team_name'])
            rider.save(update_fields=['current_team'])
        Ranking.objects.update_or_create(
            kind=Ranking.Kind.PCS, year=year, gender=gender, rider=rider,
            defaults={'rank': r['rank'], 'points': r['points'], 'previous_rank': r['previous_rank']},
        )
        saved += 1
    _log('ranking', f'pcs/{gender}/{year}', SyncLog.Status.OK, f'{saved} lignes')
    return saved


def get_jersey_wearers(race):
    """Porteurs de maillots après la dernière étape disputée, labellisés par ordre
    conventionnel (Leader, Points, Montagne, Jeunes…). Renvoie [{rider,label,color}]."""
    from datetime import date as _date
    from core.parsers.stage import parse_jersey_wearers
    candidates = list(race.stages.filter(date__lte=_date.today()).order_by('-number')) \
        or list(race.stages.order_by('-number'))
    for st in candidates:
        url = f'{pcs_client.PCS_BASE_URL}/race/{race.slug}/{race.year}/stage-{st.number}'
        soup = pcs_client.get_soup(url, cache_ttl=300)
        if not soup:
            continue
        wearers = parse_jersey_wearers(soup)
        if wearers:
            out = []
            for i, w in enumerate(wearers):
                rider = get_or_create_rider(w['slug'], w['name'])
                if not rider:
                    continue
                label, color = JERSEY_LABELS[i] if i < len(JERSEY_LABELS) else (f'Maillot {i + 1}', 'slate')
                out.append({'rider': rider, 'label': label, 'color': color})
            return out
    return []


def backfill_profile_from_image(stage):
    """Reconstruit elevation_points depuis l'image JPG (étape déjà synchro sans profil)."""
    if stage.elevation_points or not stage.profile_image_url:
        return False
    from core.profile_from_image import extract_elevation_from_image
    img = pcs_client.fetch_bytes(stage.profile_image_url, cache_ttl=7 * 86400)
    if not img:
        return False
    pts = extract_elevation_from_image(img)
    if pts:
        stage.elevation_points = pts
        stage.save(update_fields=['elevation_points'])
        return True
    return False


def sync_oneday_result(race, force=False):
    """Récupère le résultat d'une course d'un jour (classement unique, stage=None)."""
    for suffix in ('result', ''):
        url = f'{pcs_client.PCS_BASE_URL}/race/{race.slug}/{race.year}/{suffix}'.rstrip('/')
        soup = pcs_client.get_soup(url, cache_ttl=300, force=force)
        if soup and soup.find('table', class_='results'):
            rows = parse_results_table(soup)
            saved = _save_results(race, rows, ClassificationType.STAGE, stage=None)
            leader = next((x for x in rows if x['rank'] == 1), None)
            if leader:
                race.winner = get_or_create_rider(leader['rider_slug'], leader['rider_name'])
                race.save(update_fields=['winner'])
            _log('results', f'{race.slug}/{race.year}/result',
                 SyncLog.Status.OK if saved else SyncLog.Status.EMPTY, f'{saved} résultats')
            return saved
    return 0


_CLASSIF_URLS = {
    ClassificationType.POINTS: 'points',
    ClassificationType.KOM: 'kom',
    ClassificationType.YOUTH: 'youth',
}


def sync_classifications(race, force=False):
    """Récupère points / montagne / jeunes (server-side, courses terminées)."""
    total = 0
    for classif, slug in _CLASSIF_URLS.items():
        url = f'{pcs_client.PCS_BASE_URL}/race/{race.slug}/{race.year}/{slug}'
        soup = pcs_client.get_soup(url, cache_ttl=300, force=force)
        if not soup:
            continue
        rows = parse_results_table(soup)
        if rows:
            total += _save_results(race, rows, classif)
    if total:
        _log('results', f'{race.slug}/{race.year}/classifs', SyncLog.Status.OK, f'{total} lignes')
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

    # Repli : si pas de profil vectoriel (étape future), on reconstruit la
    # silhouette d'altitude depuis l'image de profil PCS (analyse de pixels).
    if not stage.elevation_points and stage.profile_image_url:
        from core.profile_from_image import extract_elevation_from_image
        img = pcs_client.fetch_bytes(stage.profile_image_url, cache_ttl=7 * 86400, force=force)
        if img:
            pts = extract_elevation_from_image(img)
            if pts:
                stage.elevation_points = pts

    stage.detail_synced_at = timezone.now()
    stage.save()
    _log('stage', f'{stage.race.slug}/{stage.race.year}/{stage.number}', SyncLog.Status.OK,
         f'{len(stage.elevation_points)} pts profil', int((time.monotonic() - t0) * 1000))
    return stage
