from datetime import datetime, timezone

import pytest
from django.test import TestCase, override_settings

from providers.capabilities import ProviderCapability
from providers.exceptions import ProviderCapabilityNotSupported, ProviderDisabled, ProviderRateLimited
from providers.http import parse_retry_after
from providers.interfaces import CalendarQuery, CyclingProvider, ProviderBatch
from providers.models import Provider, ProviderEntityMapping, ProviderSnapshot
from providers.registry import ProviderRegistry
from providers.utils import create_snapshot, snapshot_payload_hash


class DummyProvider(CyclingProvider):
    key = 'dummy'
    capabilities = frozenset({ProviderCapability.CALENDAR})

    def fetch_calendar(self, query):
        self._require(ProviderCapability.CALENDAR)
        return ProviderBatch(
            provider_key=self.key,
            capability=ProviderCapability.CALENDAR,
            observed_at=datetime.now(timezone.utc),
            records=({'year': query.year},),
        )


class ProviderFrameworkTests(TestCase):
    def test_capability_contract_raises_explicit_business_error(self):
        provider = DummyProvider()
        batch = provider.fetch_calendar(CalendarQuery(year=2026))
        assert batch.records == ({'year': 2026},)
        with pytest.raises(ProviderCapabilityNotSupported):
            provider.fetch_results(object())

    def test_registry_respects_enabled_settings(self):
        registry = ProviderRegistry()
        registry.register(DummyProvider())
        with override_settings(PROVIDERS_ENABLED=[]):
            with pytest.raises(ProviderDisabled):
                registry.get('dummy')
        with override_settings(PROVIDERS_ENABLED=['dummy']):
            assert registry.get('dummy').key == 'dummy'
            assert [p.key for p in registry.enabled()] == ['dummy']

    def test_models_persist_mappings_snapshots_and_legacy_disabled(self):
        legacy = Provider.objects.get(key='legacy-pcs')
        assert legacy.enabled is False
        assert legacy.provider_type == 'legacy'
        mapping = ProviderEntityMapping.objects.create(
            provider=legacy,
            entity_type=ProviderEntityMapping.EntityType.RIDER,
            external_id='123',
            canonical_model='catalog.Rider',
            canonical_id=1,
        )
        snapshot = create_snapshot(
            provider=legacy,
            capability='RIDERS',
            resource_type='rider',
            resource_key='123',
            observed_at=datetime.now(timezone.utc),
            payload={'external_id': '123'},
        )
        assert mapping.public_id
        assert ProviderSnapshot.objects.get(pk=snapshot.pk).payload_hash == snapshot_payload_hash({'external_id': '123'})

    def test_retry_after_parsing(self):
        assert parse_retry_after('42') == 42
        assert parse_retry_after('not-a-date') is None

    def test_rate_limit_exception_exposes_retry_after(self):
        exc = ProviderRateLimited(7)
        assert exc.retry_after_seconds == 7
