import logging
import time
import cloudscraper
from bs4 import BeautifulSoup
from django.core.cache import cache

logger = logging.getLogger(__name__)

PCS_BASE_URL = "https://www.procyclingstats.com"

_scraper = None


def _get_scraper():
    """Return a cloudscraper instance (bypasses Cloudflare JS challenges)."""
    global _scraper
    if _scraper is not None:
        return _scraper
    _scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'linux', 'mobile': False},
        delay=5,
    )
    _scraper.headers.update({
        'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': PCS_BASE_URL + '/',
    })
    return _scraper


def pcs_get(url, cache_timeout=3600, referer=None):
    """Fetch a PCS page with Cloudflare bypass, caching and polite delay."""
    cache_key = f"pcs_html_{url}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    scraper = _get_scraper()
    if referer:
        scraper.headers['Referer'] = referer

    max_retries = 3
    for attempt in range(max_retries):
        try:
            time.sleep(1.5 + attempt * 2)
            response = scraper.get(url, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            cache.set(cache_key, soup, cache_timeout)
            return soup
        except Exception as exc:
            msg = str(exc)
            if '403' in msg and attempt < max_retries - 1:
                logger.info("403 on attempt %d, resetting session...", attempt + 1)
                pcs_reset_session()
                scraper = _get_scraper()
                continue
            if '500' not in msg and '404' not in msg:
                logger.warning("Failed to fetch %s: %s", url, exc)
            return None


def pcs_reset_session():
    """Force a new scraper instance (call after repeated failures)."""
    global _scraper
    _scraper = None


