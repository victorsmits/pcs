from django.test import TestCase, override_settings

from providers.capabilities import ProviderCapability
from providers.exceptions import ProviderForbidden, ProviderInvalidPayload
from providers.fixture import FixtureProvider, fetch_with_fallback
from providers.manual import ManualProvider
from providers.models import ManualProviderRecord
from providers.registry import registry


@override_settings(PROVIDERS_ENABLED=['seed', 'manual', 'fixture'])
class ManualFixtureProviderTests(TestCase):
    def test_manual_provider_returns_active_records_only(self):
        ManualProviderRecord.objects.create(
            capability=ProviderCapability.RACE_SERIES.value,
            resource_key='manual-classic',
            payload={'slug': 'manual-classic', 'name': 'Manual Classic'},
            author='admin',
            justification='Correction validée',
        )
        ManualProviderRecord.objects.create(
            capability=ProviderCapability.RACE_SERIES.value,
            resource_key='inactive-classic',
            payload={'slug': 'inactive-classic'},
            active=False,
        )

        batch = ManualProvider().fetch_race_series()

        assert batch.provider_key == 'manual'
        assert batch.capability == ProviderCapability.RACE_SERIES
        assert [record['slug'] for record in batch.records] == ['manual-classic']

    def test_fixture_provider_replays_complete_live_fixture_without_network(self):
        batch = FixtureProvider(scenario='complete_race').fetch_live()
        events = [snapshot['event'] for snapshot in batch.records]

        assert 'race_reminder' in events
        assert 'race_start' in events
        assert 'attack' in events
        assert 'finish' in events
        assert 'result_corrected' in events

    def test_fixture_provider_exposes_conflicting_race_series_payloads(self):
        primary = FixtureProvider(key='fixture-primary', scenario='complete_race').fetch_race_series()
        secondary = FixtureProvider(key='fixture-secondary', scenario='conflict_source').fetch_race_series()

        assert primary.records[0]['slug'] == secondary.records[0]['slug']
        assert primary.records[0]['name'] != secondary.records[0]['name']

    def test_fixture_provider_403_is_explicit_and_does_not_bypass(self):
        provider = FixtureProvider(scenario='failing_403')

        try:
            provider.fetch_race_series()
        except ProviderForbidden as exc:
            assert '403' in str(exc)
        else:  # pragma: no cover
            raise AssertionError('ProviderForbidden expected')

    def test_fixture_provider_invalid_payload_is_explicit(self):
        provider = FixtureProvider(scenario='invalid_payload')

        try:
            provider.fetch_live()
        except ProviderInvalidPayload as exc:
            assert 'snapshots' in str(exc)
        else:  # pragma: no cover
            raise AssertionError('ProviderInvalidPayload expected')

    def test_fixture_fallback_uses_secondary_provider(self):
        batch = fetch_with_fallback(
            [FixtureProvider(key='fixture-down', scenario='failing_403'), FixtureProvider(key='fixture-fallback', scenario='conflict_source')],
            ProviderCapability.LIVE_STATE,
        )

        assert batch.provider_key == 'fixture-fallback'
        assert batch.records[0]['event'] == 'fallback_live'

    def test_manual_and_fixture_providers_are_registered(self):
        assert isinstance(registry.get('manual'), ManualProvider)
        assert isinstance(registry.get('fixture'), FixtureProvider)
