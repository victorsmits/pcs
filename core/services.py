import logging
import requests
from bs4 import BeautifulSoup
from django.core.cache import cache

logger = logging.getLogger(__name__)

PCS_BASE_URL = "https://www.procyclingstats.com"
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
}


def pcs_get(url, cache_timeout=3600):
    """Fetch a PCS page with caching and error handling."""
    cache_key = f"pcs_html_{url}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        cache.set(cache_key, soup, cache_timeout)
        return soup
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


def get_pcs_scraper():
    """Return pcs_scraper module or None if not available."""
    try:
        import pcs_scraper as pcs
        return pcs
    except ImportError:
        logger.warning("pcs_scraper not available")
        return None
