from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import ClassVar
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .exceptions import ProviderForbidden, ProviderRateLimited
from .models import Provider, ProviderRequestLog

SENSITIVE_HEADERS = {'authorization', 'x-api-key', 'cookie'}


def parse_retry_after(value: str | None) -> int | None:
    if not value:
        return None
    if value.isdigit():
        return int(value)
    try:
        delta = parsedate_to_datetime(value) - timezone.now()
    except (TypeError, ValueError, OverflowError):
        return None
    return max(0, int(delta.total_seconds()))


@dataclass
class ProviderHttpClient:
    provider: Provider
    timeout_seconds: float | None = None

    _recent: ClassVar[dict[str, deque[float]]] = defaultdict(deque)

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != 'https':
            raise ValueError('provider URL must use https')
        if self.provider.base_url:
            base = urlparse(self.provider.base_url)
            if parsed.netloc != base.netloc:
                raise ValueError('provider URL host does not match provider base_url')

    def _rate_limit(self) -> None:
        now = time.monotonic()
        if self.provider.min_request_interval_seconds:
            key = f'provider:min-interval:{self.provider.key}'
            last = cache.get(key)
            wait = float(self.provider.min_request_interval_seconds)
            if last and now - last < wait:
                raise ProviderRateLimited(int(wait - (now - last)) + 1)
            cache.set(key, now, timeout=max(1, int(wait * 2)))
        if self.provider.max_requests_per_minute:
            q = self._recent[self.provider.key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.provider.max_requests_per_minute:
                raise ProviderRateLimited(60 - int(now - q[0]))
            q.append(now)

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> requests.Response:
        self._validate_url(url)
        self._rate_limit()
        clean_headers = {k: v for k, v in (headers or {}).items() if k.lower() not in SENSITIVE_HEADERS}
        started = time.monotonic()
        try:
            response = requests.get(url, headers=clean_headers, timeout=self.timeout_seconds or settings.PROVIDER_HTTP_TIMEOUT_SECONDS)
            retry_after = parse_retry_after(response.headers.get('Retry-After'))
            if response.status_code == 403:
                raise ProviderForbidden('provider returned 403')
            if response.status_code == 429:
                raise ProviderRateLimited(retry_after)
            return response
        finally:
            ProviderRequestLog.objects.create(
                provider=self.provider,
                url=url,
                method='GET',
                duration_ms=int((time.monotonic() - started) * 1000),
            )
