"""Client legacy PCS désactivé par défaut.

Ce module ne doit être utilisé que pour une compatibilité transitoire locale lorsque
``PCS_LEGACY_ENABLED=True``. Le runtime normal de CycloStats ne contacte plus PCS.
"""
import logging
import time

from bs4 import BeautifulSoup
from django.conf import settings
from django.core.cache import cache

from core import pcs_circuit

logger = logging.getLogger('core')


class PCSLegacyDisabledError(RuntimeError):
    """Levée quand un appel legacy PCS est tenté alors que le kill switch est désactivé."""


class PCSAccessForbiddenError(Exception):
    """Levée quand ProCyclingStats répond explicitement HTTP 403."""

    def __init__(self, url, retry_after=None):
        self.url = url
        self.retry_after = retry_after
        super().__init__(f'PCS returned HTTP 403 for {url}')


PCSCircuitOpenError = pcs_circuit.PCSCircuitOpenError

PCS_BASE_URL = settings.PCS_BASE_URL

_session = None
_backend = None

_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': PCS_BASE_URL + '/',
}


def _ensure_legacy_enabled():
    if not getattr(settings, 'PCS_LEGACY_ENABLED', False):
        raise PCSLegacyDisabledError('Legacy PCS access is disabled by PCS_LEGACY_ENABLED=False')


def _build_session():
    global _backend
    _ensure_legacy_enabled()
    import requests
    s = requests.Session()
    s.headers.update(_HEADERS)
    _backend = 'requests'
    logger.info('PCS legacy backend: requests')
    return s


def _get_session():
    global _session
    if _session is None:
        _session = _build_session()
    return _session


def reset_session():
    """Recrée la session (à appeler après des 403 répétés)."""
    global _session, _backend
    _session = None
    _backend = None


def fetch_text(url, *, cache_ttl=3600, referer=None, force=False, max_retries=3):
    """Récupère le texte brut d'une URL PCS legacy si explicitement autorisé."""
    _ensure_legacy_enabled()
    state = pcs_circuit.current_state()
    if state.open:
        logger.warning(
            'Fetch PCS ignoré: circuit ouvert',
            extra={
                'event': 'pcs_fetch_skipped', 'url': url,
                'consecutive_failures': state.failure_count,
                'circuit_state': 'open', 'retry_after': state.retry_after,
            },
        )
        raise PCSCircuitOpenError(state.retry_after)

    cache_key = f'pcs_text::{url}'
    if not force and cache_ttl:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    session = _get_session()
    delay = settings.PCS_REQUEST_DELAY
    for attempt in range(1, max_retries + 1):
        try:
            time.sleep(delay + (attempt - 1) * 2)
            if referer:
                session.headers['Referer'] = referer
            resp = session.get(url, timeout=25)
            status_code = getattr(resp, 'status_code', None)
            if status_code == 403:
                state = pcs_circuit.record_forbidden(url, attempt=attempt, status_code=403)
                reset_session()
                raise PCSAccessForbiddenError(url, retry_after=state.retry_after)
            resp.raise_for_status()
            text = resp.text
            pcs_circuit.record_success(url)
            if cache_ttl:
                cache.set(cache_key, text, cache_ttl)
            return text
        except PCSAccessForbiddenError:
            raise
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
            if status_code == 403 or '403' in msg:
                state = pcs_circuit.record_forbidden(url, attempt=attempt, status_code=403)
                reset_session()
                raise PCSAccessForbiddenError(url, retry_after=state.retry_after) from exc
            if attempt < max_retries:
                logger.warning(
                    'Échec temporaire fetch PCS',
                    extra={
                        'event': 'pcs_temporary_network_failure', 'url': url,
                        'attempt': attempt, 'status_code': status_code,
                        'consecutive_failures': pcs_circuit.current_state().failure_count,
                        'circuit_state': 'closed', 'retry_after': None,
                    },
                )
                continue
            if '404' not in msg and '500' not in msg:
                logger.warning(
                    'Échec fetch PCS définitif',
                    extra={
                        'event': 'pcs_functional_failure', 'url': url,
                        'attempt': attempt, 'status_code': status_code,
                        'consecutive_failures': pcs_circuit.current_state().failure_count,
                        'circuit_state': 'closed', 'retry_after': None,
                    },
                )
            return None
    return None


def get_soup(url, *, cache_ttl=3600, referer=None, force=False):
    """Récupère une page PCS et renvoie un BeautifulSoup (ou None)."""
    text = fetch_text(url, cache_ttl=cache_ttl, referer=referer, force=force)
    if text is None:
        return None
    return BeautifulSoup(text, 'lxml')


def get_json(url, *, cache_ttl=10, referer=None, force=False):
    """Récupère un JSON PCS (ou None si la réponse n'est pas du JSON)."""
    import json
    text = fetch_text(url, cache_ttl=cache_ttl, referer=referer, force=force)
    if not text:
        return None
    try:
        return json.loads(text)
    except (ValueError, json.JSONDecodeError):
        logger.warning('Réponse non-JSON pour %s (probablement gated)', url)
        return None


def fetch_bytes(url, *, cache_ttl=86400, force=False):
    """Récupère le contenu binaire d'une URL legacy si explicitement autorisé."""
    _ensure_legacy_enabled()
    import base64
    cache_key = f'pcs_bytes::{url}'
    if not force and cache_ttl:
        cached = cache.get(cache_key)
        if cached is not None:
            return base64.b64decode(cached)
    session = _get_session()
    state = pcs_circuit.current_state()
    if state.open:
        raise PCSCircuitOpenError(state.retry_after)
    try:
        time.sleep(settings.PCS_REQUEST_DELAY)
        resp = session.get(url, timeout=25)
        if getattr(resp, 'status_code', None) == 403:
            state = pcs_circuit.record_forbidden(url, attempt=1, status_code=403)
            reset_session()
            raise PCSAccessForbiddenError(url, retry_after=state.retry_after)
        resp.raise_for_status()
        pcs_circuit.record_success(url)
        content = resp.content
        if cache_ttl:
            cache.set(cache_key, base64.b64encode(content).decode(), cache_ttl)
        return content
    except (PCSAccessForbiddenError, PCSCircuitOpenError):
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning('Échec fetch_bytes %s: %s', url, exc)
        return None


def abs_url(path):
    """Transforme un chemin relatif PCS en URL absolue."""
    if not path:
        return ''
    if path.startswith('http'):
        return path
    return f"{PCS_BASE_URL}/{path.lstrip('/')}"
