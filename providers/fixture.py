from __future__ import annotations

import json
from pathlib import Path

from django.utils import timezone

from .capabilities import ProviderCapability
from .exceptions import ProviderError, ProviderForbidden, ProviderInvalidPayload, ProviderRateLimited
from .interfaces import ProviderBatch, CyclingProvider, LiveQuery

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / 'tests' / 'fixtures' / 'providers'


class FixtureProvider(CyclingProvider):
    capabilities = frozenset({ProviderCapability.RACE_SERIES, ProviderCapability.LIVE_STATE})

    def __init__(self, *, key: str = 'fixture', scenario: str = 'complete_race'):
        self.key = key
        self.scenario = scenario

    def _load(self, name: str):
        path = FIXTURE_ROOT / self.scenario / name
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ProviderInvalidPayload(f'invalid fixture payload: {path}') from exc

    def _maybe_fail(self, payload: dict) -> None:
        failure = payload.get('failure')
        if failure == '403':
            raise ProviderForbidden('fixture provider returned 403')
        if failure == '429':
            raise ProviderRateLimited(payload.get('retry_after_seconds'))
        if failure in {'timeout', '5xx'}:
            raise ProviderError(f'fixture provider failure: {failure}')

    def fetch_race_series(self) -> ProviderBatch:
        self._require(ProviderCapability.RACE_SERIES)
        payload = self._load('race_series.json')
        self._maybe_fail(payload)
        records = payload.get('records')
        if not isinstance(records, list):
            raise ProviderInvalidPayload('fixture race_series records must be a list')
        return ProviderBatch(
            provider_key=self.key,
            capability=ProviderCapability.RACE_SERIES,
            observed_at=timezone.now(),
            records=tuple(records),
            raw_snapshot=payload,
        )

    def fetch_live(self, query: LiveQuery = None) -> ProviderBatch:
        self._require(ProviderCapability.LIVE_STATE)
        payload = self._load('live.json')
        self._maybe_fail(payload)
        records = payload.get('snapshots')
        if not isinstance(records, list):
            raise ProviderInvalidPayload('fixture live snapshots must be a list')
        return ProviderBatch(
            provider_key=self.key,
            capability=ProviderCapability.LIVE_STATE,
            observed_at=timezone.now(),
            records=tuple(records),
            raw_snapshot=payload,
        )


def fetch_with_fallback(providers: list[FixtureProvider], capability: ProviderCapability) -> ProviderBatch:
    errors = []
    for provider in providers:
        try:
            if capability == ProviderCapability.RACE_SERIES:
                return provider.fetch_race_series()
            if capability == ProviderCapability.LIVE_STATE:
                return provider.fetch_live()
            raise ProviderError(f'unsupported fixture fallback capability: {capability.value}')
        except ProviderError as exc:
            errors.append(f'{provider.key}:{exc}')
    raise ProviderError('; '.join(errors))
