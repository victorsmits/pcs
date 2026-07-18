from datetime import timedelta
from importlib import import_module

from django.apps import apps
from django.test import TestCase

from catalog.models import Race, RaceSeries, RaceSeriesAlias, Result, Rider, Stage, Team, TeamIdentity

backfill = import_module('catalog.migrations.0007_backfill_canonical_lot1')


class Lot1CanonicalBackfillTests(TestCase):
    def test_backfill_creates_series_aliases_team_identities_and_public_ids(self):
        rider = Rider.objects.create(slug='jane-rider', name='Jane Rider')
        team = Team.objects.create(slug='fast-team', year=2026, name='Fast Team', nationality='BE')
        race = Race.objects.create(
            slug='great-race',
            year=2026,
            name='Great Race',
            category='WE',
            country='FR',
            is_stage_race=True,
        )
        stage = Stage.objects.create(race=race, number=1, stage_type='itt')
        result = Result.objects.create(race=race, stage=stage, rider=rider, team=team, time=timedelta(hours=1))

        backfill.forwards(apps, None)

        race.refresh_from_db()
        team.refresh_from_db()
        rider.refresh_from_db()
        stage.refresh_from_db()
        result.refresh_from_db()

        assert rider.canonical_slug == 'jane-rider'
        assert rider.normalized_name == 'jane rider'
        assert team.identity is not None
        assert TeamIdentity.objects.get(canonical_slug='fast-team').current_name == 'Fast Team'
        assert race.series is not None
        assert race.official_name == 'Great Race'
        assert race.host_country == 'FR'
        assert RaceSeries.objects.get(canonical_slug='great-race').format == 'stage_race'
        assert RaceSeriesAlias.objects.filter(series=race.series, normalized_name='great race').exists()
        assert stage.stage_key == '1'
        assert stage.display_label == 'Étape 1'
        assert stage.stage_kind == 'itt'
        assert result.elapsed_time_ms == 3_600_000
        assert result.raw_display_time == ''
