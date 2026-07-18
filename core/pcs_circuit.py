"""Circuit breaker partagé pour les accès ProCyclingStats.

L'état est stocké dans le cache Django. En production, ce cache est Redis : les
clés gardent volontairement le préfixe demandé par l'exploitation pour faciliter
l'observation et les interventions manuelles.
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('core')

OPEN_KEY = 'pcs:circuit:open'
FAILURE_COUNT_KEY = 'pcs:circuit:failure_count'
RETRY_AFTER_KEY = 'pcs:circuit:retry_after'
ALERTED_KEY = 'pcs:circuit:alerted'

DEFAULT_BACKOFFS = (60, 300, 900, 1800, 3600)


class PCSCircuitOpenError(Exception):
    """Levée quand le circuit PCS est ouvert et que le polling doit attendre."""

    def __init__(self, retry_after=None):
        self.retry_after = retry_after
        super().__init__(f'Circuit PCS ouvert jusqu’à {retry_after}')


@dataclass(frozen=True)
class CircuitState:
    open: bool
    failure_count: int
    retry_after: float | None

    @property
    def retry_in(self) -> int:
        if not self.retry_after:
            return 0
        return max(0, int(self.retry_after - time.time()))


def _threshold() -> int:
    return int(getattr(settings, 'PCS_403_THRESHOLD', 2))


def _backoffs() -> tuple[int, ...]:
    raw = getattr(settings, 'PCS_CIRCUIT_BACKOFFS', DEFAULT_BACKOFFS)
    if isinstance(raw, str):
        values = [int(x.strip()) for x in raw.split(',') if x.strip()]
        return tuple(values) or DEFAULT_BACKOFFS
    return tuple(raw) or DEFAULT_BACKOFFS


def _jitter_ratio() -> float:
    return float(getattr(settings, 'PCS_CIRCUIT_JITTER', 0.15))


def current_state() -> CircuitState:
    retry_after = cache.get(RETRY_AFTER_KEY)
    is_open = bool(cache.get(OPEN_KEY))
    if is_open and retry_after and float(retry_after) <= time.time():
        cache.delete(OPEN_KEY)
        is_open = False
    return CircuitState(
        open=is_open,
        failure_count=int(cache.get(FAILURE_COUNT_KEY) or 0),
        retry_after=float(retry_after) if retry_after else None,
    )


def is_open() -> bool:
    return current_state().open


def retry_after() -> float | None:
    return current_state().retry_after


def _duration_for_failure_count(failures: int) -> int:
    backoffs = _backoffs()
    index = max(0, min(failures - _threshold(), len(backoffs) - 1))
    base = backoffs[index]
    jitter = base * _jitter_ratio()
    return max(1, int(base + random.uniform(-jitter, jitter)))


def open_circuit(duration: int, failures: int | None = None) -> CircuitState:
    retry_at = time.time() + duration
    cache.set(OPEN_KEY, '1', timeout=duration)
    cache.set(RETRY_AFTER_KEY, retry_at, timeout=duration + 3600)
    if failures is not None:
        cache.set(FAILURE_COUNT_KEY, int(failures), timeout=24 * 3600)
    state = current_state()
    logger.warning(
        'Circuit PCS ouvert',
        extra={
            'event': 'pcs_circuit_opened',
            'consecutive_failures': state.failure_count,
            'circuit_state': 'open',
            'retry_after': state.retry_after,
        },
    )
    _maybe_alert(state)
    return state


def record_forbidden(url: str, *, attempt: int | None = None, status_code: int = 403) -> CircuitState:
    try:
        failures = cache.incr(FAILURE_COUNT_KEY)
    except ValueError:
        cache.add(FAILURE_COUNT_KEY, 0, timeout=24 * 3600)
        failures = cache.incr(FAILURE_COUNT_KEY)
    cache.touch(FAILURE_COUNT_KEY, timeout=24 * 3600)

    state = current_state()
    if failures >= _threshold():
        state = open_circuit(_duration_for_failure_count(failures), failures)
    else:
        state = CircuitState(open=False, failure_count=failures, retry_after=state.retry_after)

    logger.warning(
        'Accès PCS refusé',
        extra={
            'event': 'pcs_access_forbidden',
            'url': url,
            'status_code': status_code,
            'attempt': attempt,
            'consecutive_failures': failures,
            'circuit_state': 'open' if state.open else 'closed',
            'retry_after': state.retry_after,
        },
    )
    _maybe_alert(state)
    return state


def record_success(url: str | None = None) -> CircuitState:
    cache.delete_many([OPEN_KEY, FAILURE_COUNT_KEY, RETRY_AFTER_KEY, ALERTED_KEY])
    logger.info(
        'Circuit PCS fermé après succès',
        extra={
            'event': 'pcs_circuit_closed',
            'url': url,
            'consecutive_failures': 0,
            'circuit_state': 'closed',
            'retry_after': None,
        },
    )
    return current_state()


def _maybe_alert(state: CircuitState) -> None:
    minutes = int(getattr(settings, 'PCS_403_ALERT_AFTER_SECONDS', 300))
    if state.failure_count < _threshold() or not state.retry_after:
        return
    first_backoff = _backoffs()[0]
    persisted_long_enough = state.failure_count >= _threshold() + 1 or state.retry_in >= minutes or first_backoff >= minutes
    if not persisted_long_enough or cache.get(ALERTED_KEY):
        return
    cache.set(ALERTED_KEY, '1', timeout=state.retry_in or minutes)
    logger.error(
        'ALERTE: blocage HTTP 403 PCS persistant',
        extra={
            'event': 'pcs_403_persistent_alert',
            'status_code': 403,
            'consecutive_failures': state.failure_count,
            'circuit_state': 'open' if state.open else 'closed',
            'retry_after': state.retry_after,
        },
    )
