from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from providers.models import Provider, ProviderAuthority, ProviderSnapshot
from providers.utils import create_snapshot

from .dto import NormalizedDTO, NormalizedRaceSeries, NormalizedRider
from .models import DataConflict, IngestionRun, SourceObservation
from .resolver import IdentityResolver, canonical_model_name
from .serialization import to_jsonable

AUTHORITY_WEIGHT = {
    ProviderAuthority.MANUAL_OVERRIDE: 100,
    ProviderAuthority.OFFICIAL: 80,
    ProviderAuthority.LICENSED: 60,
    ProviderAuthority.COMMUNITY: 30,
    ProviderAuthority.LEGACY: 10,
    ProviderAuthority.UNKNOWN: 0,
}


class MergeResult:
    def __init__(self, *, created: bool = False, updated: bool = False, conflicts: int = 0):
        self.created = created
        self.updated = updated
        self.conflicts = conflicts


class MergeEngine:
    def __init__(self, provider: Provider, run: IngestionRun | None = None):
        self.provider = provider
        self.run = run
        self.resolver = IdentityResolver(provider)

    @transaction.atomic
    def ingest(self, dto: NormalizedDTO) -> MergeResult:
        dto.validate()
        snapshot = create_snapshot(
            provider=self.provider,
            capability=getattr(self.run, 'capability', dto.entity_type.value),
            resource_type=dto.entity_type.value,
            resource_key=dto.source.external_id,
            observed_at=dto.source.observed_at or timezone.now(),
            payload=to_jsonable(dto),
            valid=True,
        )
        if isinstance(dto, NormalizedRaceSeries):
            obj, created = self.resolver.resolve_or_create_race_series(dto)
            updated, conflicts = self._merge_fields(obj, dto, ['current_name', 'gender_category', 'discipline', 'format', 'scope', 'primary_country', 'importance', 'active', 'aliases', 'metadata'])
        elif isinstance(dto, NormalizedRider):
            obj, created = self.resolver.resolve_or_create_rider(dto)
            updated, conflicts = self._merge_fields(obj, dto, ['normalized_name', 'nationality', 'gender_category', 'photo_url', 'metadata'])
            if dto.full_name and obj.name != dto.full_name:
                conflicts += self._maybe_update(obj, 'name', dto.full_name, dto, None)
        else:
            raise NotImplementedError(f'unsupported dto for Lot 3 merge: {dto.entity_type.value}')
        self.resolver.bind(dto, obj)
        self._observe(dto, obj, snapshot)
        return MergeResult(created=created, updated=updated, conflicts=conflicts)

    def _observe(self, dto: NormalizedDTO, obj, snapshot: ProviderSnapshot) -> SourceObservation:
        return SourceObservation.objects.create(
            provider=self.provider,
            entity_type=dto.entity_type.value,
            external_id=dto.source.external_id,
            payload_version=dto.source.payload_version,
            run=self.run,
            snapshot=snapshot,
            external_url=dto.source.external_url,
            canonical_model=canonical_model_name(obj),
            canonical_id=obj.pk,
            observed_at=dto.source.observed_at or timezone.now(),
            source_updated_at=dto.source.source_updated_at,
            confidence=dto.source.confidence,
            normalized_payload=to_jsonable(dto),
            raw_payload=dto.source.raw_payload,
        )

    def _merge_fields(self, obj, dto: NormalizedDTO, names: list[str]) -> tuple[bool, int]:
        updated = False
        conflicts = 0
        for name in names:
            if not hasattr(dto, name) or not hasattr(obj, name):
                continue
            incoming = getattr(dto, name)
            if incoming in ('', None, [], {}):
                continue
            current = getattr(obj, name)
            if current in ('', None, [], {}):
                setattr(obj, name, incoming)
                updated = True
            elif current != incoming:
                conflicts += self._maybe_update(obj, name, incoming, dto, current)
        if updated:
            obj.save()
        return updated, conflicts

    def _maybe_update(self, obj, field_name: str, incoming: Any, dto: NormalizedDTO, current: Any) -> int:
        current_observation = SourceObservation.objects.filter(
            canonical_model=canonical_model_name(obj), canonical_id=obj.pk, entity_type=dto.entity_type.value
        ).order_by('-confidence', '-observed_at').first()
        incoming_weight = AUTHORITY_WEIGHT.get(self.provider.authority_level, 0)
        current_weight = AUTHORITY_WEIGHT.get(current_observation.provider.authority_level, 0) if current_observation else -1
        if incoming_weight > current_weight and dto.source.confidence >= (current_observation.confidence if current_observation else 0):
            setattr(obj, field_name, incoming)
            obj.save(update_fields=[field_name, 'updated_at'] if hasattr(obj, 'updated_at') else [field_name])
            return 0
        DataConflict.objects.create(
            entity_type=dto.entity_type.value,
            canonical_model=canonical_model_name(obj),
            canonical_id=obj.pk,
            field_name=field_name,
            current_value={'value': to_jsonable(current)},
            incoming_value={'value': to_jsonable(incoming)},
            reason='incoming value differs from existing canonical value',
        )
        return 1
