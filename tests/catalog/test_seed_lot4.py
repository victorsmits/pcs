from django.core.management import call_command
from django.test import TestCase

from catalog.models import RaceScope, RaceSeries, RaceSeriesAlias
from catalog.seed_services import P1_COUNTRIES, P2_COUNTRIES, load_road_series, national_championship_entries, seed_national_championships, seed_road_series
from providers.capabilities import ProviderCapability
from providers.seed import SeedProvider


class RoadSeriesSeedTests(TestCase):
    def test_road_series_yaml_contains_required_priorities_and_championships(self):
        entries = load_road_series()
        slugs = {entry['slug'] for entry in entries}
        priorities = {entry['priority'] for entry in entries}

        assert {'P0', 'P1', 'P2', 'P3'} <= priorities
        assert 'tour-de-france' in slugs
        assert 'tour-de-france-femmes' in slugs
        assert 'world-championship:ME:road-race' in slugs
        assert 'olympic-games:WE:itt' in slugs
        assert 'european-championship:ME:itt' in slugs

    def test_seed_road_series_is_idempotent_and_keeps_aliases(self):
        before = RaceSeries.objects.count()
        seed_road_series()
        after_first = RaceSeries.objects.count()
        second = seed_road_series()

        renewi = RaceSeries.objects.get(canonical_slug='renewi-tour')
        assert after_first >= before
        assert second.created == 0
        assert RaceSeries.objects.count() == after_first
        assert renewi.importance == 'P2'
        assert RaceSeriesAlias.objects.filter(series=renewi, normalized_name='benelux-tour').exists()

    def test_national_championship_seed_creates_four_series_per_country_and_is_idempotent(self):
        expected = len(P1_COUNTRIES + P2_COUNTRIES) * 4
        assert len(national_championship_entries()) == expected

        first = seed_national_championships()
        second = seed_national_championships()

        assert first.created + first.updated == expected
        assert second.created == 0
        assert RaceSeries.objects.filter(scope=RaceScope.NATIONAL_CHAMPIONSHIP).count() == expected
        assert RaceSeries.objects.filter(canonical_slug='national-championship:BE:ME:road-race', importance='P1').exists()
        assert RaceSeries.objects.filter(canonical_slug='national-championship:JP:WE:itt', importance='P2').exists()

    def test_management_commands_are_idempotent(self):
        call_command('seed_road_series', verbosity=0)
        call_command('seed_road_series', verbosity=0)
        call_command('seed_national_championships', verbosity=0)
        call_command('seed_national_championships', verbosity=0)

        assert RaceSeries.objects.filter(canonical_slug='paris-roubaix').count() == 1
        assert RaceSeries.objects.filter(canonical_slug='national-championship:FR:WE:itt').count() == 1

    def test_seed_provider_exposes_race_series_without_network(self):
        provider = SeedProvider()
        batch = provider.fetch_race_series()

        assert batch.provider_key == 'seed'
        assert batch.capability == ProviderCapability.RACE_SERIES
        assert len(batch.records) == len(load_road_series())
