from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from django.utils.text import slugify


class ValidationError(ValueError):
    pass


class NormalizedEntityType(StrEnum):
    RACE_SERIES = 'race_series'
    RACE_EDITION = 'race_edition'
    STAGE = 'stage'
    RIDER = 'rider'
    TEAM_IDENTITY = 'team_identity'
    TEAM_SEASON = 'team_season'
    STARTLIST_ENTRY = 'startlist_entry'
    RESULT = 'result'
    CLASSIFICATION = 'classification'
    LIVE_SNAPSHOT = 'live_snapshot'
    LIVE_GROUP = 'live_group'
    LIVE_EVENT = 'live_event'


@dataclass(frozen=True)
class SourceMetadata:
    provider_key: str
    external_id: str
    external_url: str = ''
    observed_at: datetime | None = None
    source_updated_at: datetime | None = None
    confidence: Decimal = Decimal('1.0')
    payload_version: str = '1'
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.provider_key:
            raise ValidationError('provider_key is required')
        if not self.external_id:
            raise ValidationError('external_id is required')
        if self.confidence < 0 or self.confidence > 1:
            raise ValidationError('confidence must be between 0 and 1')


@dataclass(frozen=True)
class NormalizedDTO:
    source: SourceMetadata

    entity_type: NormalizedEntityType = field(init=False)

    def validate(self) -> None:
        self.source.validate()


@dataclass(frozen=True)
class NormalizedRaceSeries(NormalizedDTO):
    canonical_slug: str
    current_name: str
    gender_category: str = 'ME'
    discipline: str = 'road'
    format: str = 'one_day'
    scope: str = 'regular'
    primary_country: str = ''
    importance: str = 'P3'
    active: bool = True
    aliases: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    entity_type: NormalizedEntityType = field(init=False, default=NormalizedEntityType.RACE_SERIES)

    def validate(self) -> None:
        super().validate()
        if not self.current_name:
            raise ValidationError('current_name is required')
        if slugify(self.canonical_slug) != self.canonical_slug:
            raise ValidationError('canonical_slug must be slugified')


@dataclass(frozen=True)
class NormalizedRaceEdition(NormalizedDTO):
    series_external_id: str
    year: int
    official_name: str
    classification: str = ''
    status: str = 'unknown'
    start_date: date | None = None
    end_date: date | None = None
    host_country: str = ''
    start_location: str = ''
    finish_location: str = ''
    distance_km: Decimal | None = None
    is_stage_race: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    entity_type: NormalizedEntityType = field(init=False, default=NormalizedEntityType.RACE_EDITION)

    def validate(self) -> None:
        super().validate()
        if self.year < 1800:
            raise ValidationError('year is invalid')
        if not self.series_external_id:
            raise ValidationError('series_external_id is required')


@dataclass(frozen=True)
class NormalizedRider(NormalizedDTO):
    full_name: str
    normalized_name: str
    canonical_slug: str = ''
    birthdate: date | None = None
    nationality: str = ''
    gender_category: str = 'ME'
    height_cm: Decimal | None = None
    weight_kg: Decimal | None = None
    photo_url: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)
    entity_type: NormalizedEntityType = field(init=False, default=NormalizedEntityType.RIDER)

    def validate(self) -> None:
        super().validate()
        if not self.full_name:
            raise ValidationError('full_name is required')
        if not self.normalized_name:
            raise ValidationError('normalized_name is required')


@dataclass(frozen=True)
class NormalizedStage(NormalizedDTO):
    edition_external_id: str
    stage_key: str
    sequence: Decimal
    display_label: str
    stage_kind: str = 'road'
    date: date | None = None
    departure: str = ''
    arrival: str = ''
    distance_km: Decimal | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    entity_type: NormalizedEntityType = field(init=False, default=NormalizedEntityType.STAGE)


@dataclass(frozen=True)
class NormalizedResult(NormalizedDTO):
    edition_external_id: str
    rider_external_id: str
    stage_external_id: str = ''
    classification: str = 'stage'
    rank: int | None = None
    status: str = 'ok'
    elapsed_time_ms: int | None = None
    gap_ms: int | None = None
    points: int | None = None
    raw_display_time: str = ''
    entity_type: NormalizedEntityType = field(init=False, default=NormalizedEntityType.RESULT)


@dataclass(frozen=True)
class NormalizedLiveEvent(NormalizedDTO):
    session_external_id: str
    canonical_type: str
    raw_text: str
    normalized_text: str = ''
    external_sequence: str = ''
    occurred_at: datetime | None = None
    km_done: Decimal | None = None
    km_to_go: Decimal | None = None
    participants: list[str] = field(default_factory=list)
    status: str = 'provisional'
    entity_type: NormalizedEntityType = field(init=False, default=NormalizedEntityType.LIVE_EVENT)
