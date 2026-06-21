"""Déclencheurs de notifications push depuis le moteur live.

Chaque évènement (départ, arrivée, moment clé, rappel) n'est notifié qu'une
fois par session grâce aux drapeaux notified_* / last_notified_event_seq.
Tout est sans effet si le push est désactivé (clés VAPID absentes).
"""
import logging

from django.urls import reverse
from django.utils import timezone

from live import push

logger = logging.getLogger('live')

# Fenêtre du rappel « bientôt en course » (cadence discover ~10 min → 18 min couvre).
REMINDER_WINDOW_MIN = 18

# Mots-clés → (libellé, emoji) pour les moments clés de la timeline.
_EVENT_RULES = [
    (('chute', 'crash', 'tombe', 'tombé', 'fall ', 'crashed'), 'Chute', '⚠️'),
    (('flamme rouge', 'last kilometer', 'last kilometre', '1 km to go',
      'dernier kilomètre', 'derniers kilomètres', 'final kilometer'),
     'Derniers kilomètres', '🔔'),
    (('final climb', 'montée finale', 'foot of the', 'pied de la',
      'début de la montée'), 'Ascension finale', '⛰️'),
]


def _stage_live_url(stage):
    return reverse('live:stage_live', args=[stage.race.slug, stage.race.year, stage.number])


def _classify_event(text):
    t = (text or '').lower()
    for kws, label, emoji in _EVENT_RULES:
        if any(k in t for k in kws):
            return label, emoji
    return None


def _max_seq(session):
    seq = (session.events.exclude(seqnr=None).order_by('-seqnr')
           .values_list('seqnr', flat=True).first())
    return seq or 0


def _within_reminder_window(start_time):
    """True si l'heure de départ (CET « HH:MM ») est dans la fenêtre de rappel."""
    try:
        hh, mm = (int(x) for x in start_time.split(':')[:2])
    except (ValueError, TypeError, AttributeError):
        return False
    now = timezone.localtime()
    start = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    delta = (start - now).total_seconds()
    return 0 < delta <= REMINDER_WINDOW_MIN * 60


def _stage_winner_name(stage):
    """Nom du vainqueur d'étape (déclenche une synchro résultats si besoin)."""
    from catalog import services as catalog_services
    try:
        if not stage.winner_id:
            catalog_services.sync_stage_results(stage)
            stage.refresh_from_db()
    except Exception:  # noqa: BLE001
        pass
    return stage.winner.name if stage.winner_id and stage.winner else ''


def process_session_notifications(session, prev_status, prev_finished, new_seqs):
    """Évalue et envoie les notifications dues pour une session live."""
    if not push.push_enabled():
        return
    stage = session.stage
    race = stage.race
    url = _stage_live_url(stage)
    label = f'étape {stage.number}'
    changed = []

    # 1) Départ : première fois qu'on voit la course « racing ».
    if session.race_status == 'racing' and not session.notified_start:
        push.notify_race_followers(
            race, title=f'🚴 {race.name}',
            body=f"{label.capitalize()} : c'est parti !",
            url=url, tag=f'start-{session.id}')
        session.notified_start = True
        # Baseline : on ne renotifie pas la timeline historique comme « moments clés ».
        session.last_notified_event_seq = _max_seq(session)
        changed += ['notified_start', 'last_notified_event_seq']

    # 2) Arrivée / vainqueur.
    if session.finished and not session.notified_finish:
        winner = _stage_winner_name(stage)
        body = (f"🏆 {winner} remporte l'étape {stage.number}."
                if winner else f"L'{label} est terminée.")
        push.notify_race_followers(
            race, title=f'Arrivée — {race.name}', body=body,
            url=url, tag=f'finish-{session.id}')
        session.notified_finish = True
        changed.append('notified_finish')

    # 3) Rappel « bientôt en course » (avant le départ).
    elif (not session.finished and session.race_status != 'racing'
          and not session.notified_reminder and session.start_time
          and _within_reminder_window(session.start_time)):
        push.notify_race_followers(
            race, title='⏱️ Bientôt en course',
            body=f'{race.name} — {label} part à {session.start_time}.',
            url=url, tag=f'soon-{session.id}')
        session.notified_reminder = True
        changed.append('notified_reminder')

    # 4) Moments clés (uniquement en course, après le départ).
    if session.race_status == 'racing' and session.notified_start and new_seqs:
        fresh = [s for s in new_seqs if s and s > session.last_notified_event_seq]
        if fresh:
            key = None
            for ev in session.events.filter(seqnr__in=fresh).order_by('-seqnr'):
                hit = _classify_event(ev.text or ev.html)
                if hit:
                    key = (ev, hit)
                    break
            session.last_notified_event_seq = max(fresh)
            if 'last_notified_event_seq' not in changed:
                changed.append('last_notified_event_seq')
            if key:
                ev, (lbl, emoji) = key
                push.notify_race_followers(
                    race, title=f'{emoji} {race.name} — {lbl}',
                    body=(ev.text or '').strip()[:140] or lbl,
                    url=url, tag=f'evt-{session.id}')

    if changed:
        session.save(update_fields=list(dict.fromkeys(changed)))
