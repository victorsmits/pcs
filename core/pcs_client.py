"""Client HTTP PCS avec contournement Cloudflare, cache et politesse.

Backends, par ordre de préférence : curl_cffi (meilleur fingerprint TLS) →
cloudscraper → requests. La session est globale et réutilisée.
"""
import logging
import time

from bs4 import BeautifulSoup
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('core')

PCS_BASE_URL = settings.PCS_BASE_URL

_session = None
_backend = None

_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': PCS_BASE_URL + '/',
}


def _build_session():
    global _backend
    try:
        from curl_cffi.requests import Session
        _backend = 'curl_cffi'
        logger.info('PCS backend: curl_cffi')
        return Session(impersonate='chrome', headers=_HEADERS)
    except ImportError:
        pass
    try:
        import cloudscraper
        s = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'linux', 'mobile': False}, delay=5,
        )
        s.headers.update(_HEADERS)
        _backend = 'cloudscraper'
        logger.info('PCS backend: cloudscraper')
        return s
    except ImportError:
        pass
    import requests
    s = requests.Session()
    s.headers.update(_HEADERS)
    _backend = 'requests'
    logger.warning('PCS backend: requests (Cloudflare bypass improbable)')
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
    """Récupère le texte brut d'une URL PCS (avec cache + retries). Renvoie str ou None."""
    cache_key = f'pcs_text::{url}'
    if not force and cache_ttl:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    session = _get_session()
    delay = settings.PCS_REQUEST_DELAY
    for attempt in range(max_retries):
        try:
            time.sleep(delay + attempt * 2)
            if referer:
                session.headers['Referer'] = referer
            resp = session.get(url, timeout=25)
            resp.raise_for_status()
            text = resp.text
            if cache_ttl:
                cache.set(cache_key, text, cache_ttl)
            return text
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if '403' in msg and attempt < max_retries - 1:
                logger.info('403 sur %s (essai %d/%d), reset session…', url, attempt + 1, max_retries)
                reset_session()
                session = _get_session()
                continue
            if '404' not in msg and '500' not in msg:
                logger.warning('Échec fetch %s: %s', url, exc)
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


def abs_url(path):
    """Transforme un chemin relatif PCS en URL absolue."""
    if not path:
        return ''
    if path.startswith('http'):
        return path
    return f"{PCS_BASE_URL}/{path.lstrip('/')}"
