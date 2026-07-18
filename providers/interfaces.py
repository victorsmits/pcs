from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .capabilities import ProviderCapability
from .exceptions import ProviderCapabilityNotSupported


@dataclass(frozen=True)
class ProviderHealth:
    status: str
    checked_at: datetime | None = None
    message: str = ''


@dataclass(frozen=True)
class ProviderBatch:
    provider_key: str
    capability: ProviderCapability
    observed_at: datetime
    records: tuple[Any, ...] = field(default_factory=tuple)
    raw_snapshot: dict[str, Any] | list[Any] | None = None


@dataclass(frozen=True)
class CalendarQuery:
    year: int | None = None


@dataclass(frozen=True)
class RaceEditionQuery:
    external_id: str | None = None
    public_id: str | None = None

StageQuery = RaceEditionQuery
StartListQuery = RaceEditionQuery
ResultsQuery = RaceEditionQuery
LiveQuery = RaceEditionQuery


class CyclingProvider(ABC):
    key: str
    capabilities: frozenset[ProviderCapability] = frozenset()

    def supports(self, capability: ProviderCapability) -> bool:
        return capability in self.capabilities

    def _require(self, capability: ProviderCapability) -> None:
        if not self.supports(capability):
            raise ProviderCapabilityNotSupported(f'{self.key} does not support {capability.value}')

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(status='unknown')

    def fetch_calendar(self, query: CalendarQuery) -> ProviderBatch:
        self._require(ProviderCapability.CALENDAR)
        raise NotImplementedError

    def fetch_race_edition(self, query: RaceEditionQuery) -> ProviderBatch:
        self._require(ProviderCapability.RACE_EDITIONS)
        raise NotImplementedError

    def fetch_stages(self, query: StageQuery) -> ProviderBatch:
        self._require(ProviderCapability.STAGES)
        raise NotImplementedError

    def fetch_startlist(self, query: StartListQuery) -> ProviderBatch:
        self._require(ProviderCapability.STARTLIST)
        raise NotImplementedError

    def fetch_results(self, query: ResultsQuery) -> ProviderBatch:
        self._require(ProviderCapability.RESULTS)
        raise NotImplementedError

    def fetch_live(self, query: LiveQuery) -> ProviderBatch:
        self._require(ProviderCapability.LIVE_STATE)
        raise NotImplementedError
