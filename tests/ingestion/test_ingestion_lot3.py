from datetime import datetime, timezone
from decimal import Decimal

import pytest
from django.test import TestCase

from catalog.models import RaceSeries
from ingestion.dto import NormalizedRaceSeries, NormalizedRider, SourceMetadata, ValidationError
from ingestion.merge import MergeEngine
from ingestion.models import DataConflict, IngestionRun, SourceObservation
from ingestion.orchestrator import IngestionOrchestrator
from providers.capabilities import ProviderCapability
from providers.interfaces import ProviderBatch
from providers.models import Provider, ProviderAuthority, ProviderEntityMapping, ProviderType


class IngestionLot3Tests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(
            key='fixture-official',
            name='Fixture Official',
            provider_type=ProviderType.FIXTURE,
            enabled=True,
            authority_level=ProviderAuthority.OFFICIAL,
            capabilities=[ProviderCapability.RACE_SERIES.value],
        )

    def source(self, external_id='race-1'):
        return SourceMetadata(
            provider_key=self.provider.key,
            external_id=external_id,
            observed_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
            confidence=Decimal('0.9'),
        )

    def test_dto_validation_rejects_missing_provider(self):
        dto = NormalizedRaceSeries(source=SourceMetadata(provider_key='', external_id='x'), canonical_slug='race', current_name='Race')
        with pytest.raises(ValidationError):
            dto.validate()

    def test_merge_creates_series_mapping_snapshot_and_observation(self):
        dto = NormalizedRaceSeries(source=self.source(), canonical_slug='great-race', current_name='Great Race', importance='P1')
        result = MergeEngine(self.provider).ingest(dto)

        series = RaceSeries.objects.get(canonical_slug='great-race')
        assert result.created is True
        assert series.importance == 'P1'
        assert ProviderEntityMapping.objects.filter(provider=self.provider, external_id='race-1', canonical_id=series.pk).exists()
        assert SourceObservation.objects.filter(provider=self.provider, external_id='race-1', canonical_id=series.pk).exists()
        assert self.provider.snapshots.filter(resource_type='race_series', resource_key='race-1', valid=True).exists()

    def test_merge_creates_conflict_for_lower_authority_difference(self):
        dto = NormalizedRaceSeries(source=self.source(), canonical_slug='great-race', current_name='Great Race')
        MergeEngine(self.provider).ingest(dto)
        community = Provider.objects.create(
            key='fixture-community',
            name='Fixture Community',
            provider_type=ProviderType.FIXTURE,
            enabled=True,
            authority_level=ProviderAuthority.COMMUNITY,
            capabilities=[ProviderCapability.RACE_SERIES.value],
        )
        changed = NormalizedRaceSeries(
            source=SourceMetadata(provider_key=community.key, external_id='race-2', observed_at=datetime(2026, 7, 18, tzinfo=timezone.utc)),
            canonical_slug='great-race',
            current_name='Great Race Renamed',
        )

        result = MergeEngine(community).ingest(changed)

        assert result.conflicts == 1
        assert RaceSeries.objects.get(canonical_slug='great-race').current_name == 'Great Race'
        assert DataConflict.objects.filter(entity_type='race_series', field_name='current_name', status='open').exists()

    def test_orchestrator_records_run_counts(self):
        dto = NormalizedRaceSeries(source=self.source('race-3'), canonical_slug='third-race', current_name='Third Race')
        batch = ProviderBatch(
            provider_key=self.provider.key,
            capability=ProviderCapability.RACE_SERIES,
            observed_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
            records=(dto,),
        )

        run = IngestionOrchestrator().sync_batch(provider=self.provider, batch=batch, resource_type='race_series')

        assert run.status == 'success'
        assert run.records_received == 1
        assert run.records_created == 1
        assert IngestionRun.objects.get(pk=run.pk).finished_at is not None

    def test_rider_identity_reuses_external_mapping(self):
        dto = NormalizedRider(
            source=self.source('rider-1'),
            full_name='Jane Doe',
            normalized_name='jane doe',
            nationality='FR',
            gender_category='WE',
        )
        first = MergeEngine(self.provider).ingest(dto)
        replay = MergeEngine(self.provider).ingest(dto)

        assert first.created is True
        assert replay.created is False
        assert ProviderEntityMapping.objects.filter(entity_type='rider', external_id='rider-1').count() == 1
