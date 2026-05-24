import logging
import time
from bs4 import BeautifulSoup
from django.core.cache import cache

logger = logging.getLogger(__name__)

PCS_BASE_URL = "https://www.procyclingstats.com"

_session = None
_backend = None  # 'curl_cffi' or 'cloudscraper'

_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': PCS_BASE_URL + '/',
}


def _get_session():
    """Return an HTTP session with Cloudflare bypass (curl_cffi preferred, cloudscraper fallback)."""
    global _session, _backend
    if _session is not None:
        return _session

    # Try curl_cffi first (best TLS fingerprint impersonation)
    try:
        from curl_cffi.requests import Session
        _session = Session(impersonate="chrome", headers=_HEADERS)
        _backend = 'curl_cffi'
        logger.info("Using curl_cffi backend for PCS scraping")
        return _session
    except ImportError:
        pass

    # Fallback to cloudscraper
    try:
        import cloudscraper
        _session = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'linux', 'mobile': False},
            delay=5,
        )
        _session.headers.update(_HEADERS)
        _backend = 'cloudscraper'
        logger.info("Using cloudscraper backend for PCS scraping")
        return _session
    except ImportError:
        pass

    # Last resort: plain requests
    import requests
    _session = requests.Session()
    _session.headers.update(_HEADERS)
    _backend = 'requests'
    logger.warning("Using plain requests backend (Cloudflare bypass unlikely)")
    return _session


def pcs_get(url, cache_timeout=3600, referer=None, force=False):
    """Fetch a PCS page with Cloudflare bypass, caching and polite delay.

    Args:
        url: URL to fetch.
        cache_timeout: Cache TTL in seconds (0 = no cache).
        referer: Optional Referer header override.
        force: If True, bypass the cache and always fetch fresh.
    """
    cache_key = f"pcs_html_{url}"
    if not force:
        cached = cache.get(cache_key)
        if cached:
            return cached

    session = _get_session()

    max_retries = 3
    for attempt in range(max_retries):
        try:
            time.sleep(1.5 + attempt * 2)
            if referer:
                session.headers['Referer'] = referer
            response = session.get(url, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            if cache_timeout > 0:
                cache.set(cache_key, soup, cache_timeout)
            return soup
        except Exception as exc:
            msg = str(exc)
            if '403' in msg and attempt < max_retries - 1:
                logger.info("403 on attempt %d/%d, resetting session...", attempt + 1, max_retries)
                pcs_reset_session()
                session = _get_session()
                continue
            if '500' not in msg and '404' not in msg:
                logger.warning("Failed to fetch %s: %s", url, exc)
            return None


def pcs_reset_session():
    """Force a new session instance (call after repeated failures)."""
    global _session, _backend
    _session = None
    _backend = None


