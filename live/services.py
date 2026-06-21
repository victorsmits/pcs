"""Service de synchronisation live : poll d'une étape et mise à jour de l'état."""
import logging
import re
import time

from django.utils import timezone

from core import pcs_client
from core.models import SyncLog
from core.parsers.live import parse_live_page
from core.parsers.profile import extract_elevation_points
from catalog.models import Race, Stage
from live.models import LiveSession, LiveGroup, LiveEvent

logger = logging.getLogger('live')

_LIVE_HREF_RE = re.compile(r'/race/([^/]+)/(\d+)/stage-(\d+)/live')


def discover_live_today():
    """Lit la home PCS, repère les étapes live/soon du jour, (dés)active les LiveSession.

    Renvoie {'active': n, 'created': n}.
    """
    soup = pcs_client.get_soup(f'{pcs_client.PCS_BASE_URL}/', cache_ttl=60, force=True)
    if not soup:
        return {'active': 0, 'created': 0}

    found = {}  # (slug, year, number) -> status
    for a in soup.find_all('a', href=True):
        m = _LIVE_HREF_RE.search('/' + a['href'].lstrip('/'))
        if not m:
            continue
        slug, year, number = m.group(1), int(m.group(2)), int(m.group(3))
        txt = a.get_text(' ', strip=True).lower()
        status = 'live' if txt.startswith('live') else ('soon' if txt.startswith('soon') else 'other')
        # priorité à 'live' si doublon
        key = (slug, year, number)
        if key not in found or status == 'live':
            found[key] = status

    active, created = 0, 0
    live_stage_ids = []
    for (slug, year, number), status in found.items():
        if status not in ('live', 'soon'):
            continue
        race = Race.objects.filter(slug=slug, year=year).first()
        if not race:
            continue
        stage, was_created = Stage.objects.get_or_create(race=race, number=number)
        created += int(was_created)
        session, _ = LiveSession.objects.get_or_create(stage=stage)
        session.is_active = True
        session.save(update_fields=['is_active'])
        live_stage_ids.append(stage.id)
        active += 1

    # Désactive les sessions qui ne sont plus dans la liste du jour
    LiveSession.objects.filter(is_active=True).exclude(stage_id__in=live_stage_ids).update(is_active=False)

    SyncLog.objects.create(entity_type='live', ref='discover',
                           status=SyncLog.Status.OK, message=f'{active} actives, {created} étapes créées')
    return {'active': active, 'created': created}


def live_url(stage):
    return (f'{pcs_client.PCS_BASE_URL}/race/{stage.race.slug}/'
            f'{stage.race.year}/stage-{stage.number}/live')


def sync_live_session(stage, force=True):
    """Récupère la page live d'une étape et met à jour LiveSession/Groups/Events.

    Renvoie le LiveSession (ou None si échec).
    """
    t0 = time.monotonic()
    url = live_url(stage)
    # cache_ttl court : on veut du quasi temps-réel
    html = pcs_client.fetch_text(url, cache_ttl=10, force=force, referer=url)
    if not html:
        _log_live(stage, SyncLog.Status.ERROR, 'fetch échoué')
        return None

    parsed = parse_live_page(html)
    state = parsed['state']
    if not state:
        _log_live(stage, SyncLog.Status.EMPTY, 'pas de var data')
        return None

    session, _ = LiveSession.objects.get_or_create(stage=stage)
    prev_status, prev_finished = session.race_status, session.finished
    for field, value in state.items():
        setattr(session, field, value)
    session.raw_data = parsed['data']
    session.last_polled_at = timezone.now()
    session.is_active = state['race_status'] == 'racing' and not state['finished']
    session.save()

    # Profil (si l'étape n'a pas encore ses points)
    if not stage.elevation_points:
        pts = extract_elevation_points(html)
        if pts:
            stage.elevation_points = pts
            stage.save(update_fields=['elevation_points'])

    # Groupes : on remplace l'instantané courant
    session.groups.all().delete()
    front_pct = state.get('perc')
    for g in parsed['groups']:
        LiveGroup.objects.create(
            session=session, order=g['order'], label=g['label'][:80],
            gap=g['gap'][:20], rider_count=g['rider_count'], riders=g['riders'],
            profile_pct=front_pct if g['order'] == 0 else None,
        )

    # Timeline : insertion incrémentale par seqnr (dédupe en base + dans le batch)
    existing = set(session.events.values_list('seqnr', flat=True))
    to_create = []
    for ev in parsed['timeline']:
        seq = ev['seqnr']
        if seq is None or seq in existing:
            continue
        existing.add(seq)
        to_create.append(LiveEvent(
            session=session, seqnr=seq, marker=ev['marker'],
            text=ev['text'], html=ev['html'], order=seq,
        ))
    new_events = len(to_create)
    if to_create:
        LiveEvent.objects.bulk_create(to_create, ignore_conflicts=True)

    # Notifications push (départ / arrivée / moments clés / rappel) — best-effort.
    try:
        from live.notifications import process_session_notifications
        process_session_notifications(
            session, prev_status, prev_finished,
            [ev.seqnr for ev in to_create])
    except Exception:  # noqa: BLE001 — ne jamais casser le poll live
        logger.exception('Notif push échouée pour %s', stage)

    _log_live(stage, SyncLog.Status.OK,
              f"{state['race_status']} km{state.get('km_done')} +{new_events} events",
              int((time.monotonic() - t0) * 1000))
    return session


def _log_live(stage, status, message='', duration_ms=None):
    SyncLog.objects.create(
        entity_type='live',
        ref=f'{stage.race.slug}/{stage.race.year}/{stage.number}',
        status=status, message=message[:2000], duration_ms=duration_ms,
    )
