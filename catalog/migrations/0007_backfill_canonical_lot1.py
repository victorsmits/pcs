# Generated manually for Lot 1 canonical backfill.
import uuid

from django.db import migrations

def _normalize(value):
    return ' '.join((value or '').strip().lower().split())


def _stage_key(number):
    return str(number) if number is not None else ''


def forwards(apps, schema_editor):
    Rider = apps.get_model('catalog', 'Rider')
    Team = apps.get_model('catalog', 'Team')
    TeamIdentity = apps.get_model('catalog', 'TeamIdentity')
    Race = apps.get_model('catalog', 'Race')
    RaceSeries = apps.get_model('catalog', 'RaceSeries')
    RaceSeriesAlias = apps.get_model('catalog', 'RaceSeriesAlias')
    Stage = apps.get_model('catalog', 'Stage')
    StartListEntry = apps.get_model('catalog', 'StartListEntry')
    Result = apps.get_model('catalog', 'Result')

    for rider in Rider.objects.all().iterator():
        rider.public_id = uuid.uuid4()
        rider.canonical_slug = rider.slug
        rider.normalized_name = _normalize(rider.name)
        rider.save(update_fields=['public_id', 'canonical_slug', 'normalized_name'])

    identities_by_slug = {}
    for team in Team.objects.order_by('slug', '-year', 'id').iterator():
        team.public_id = uuid.uuid4()
        identity = identities_by_slug.get(team.slug)
        if identity is None:
            identity, _ = TeamIdentity.objects.get_or_create(
                canonical_slug=team.slug,
                defaults={
                    'current_name': team.name,
                    'primary_country': team.nationality,
                    'aliases': [team.name] if team.name else [],
                },
            )
            identities_by_slug[team.slug] = identity
        if team.name and team.name not in (identity.aliases or []):
            identity.aliases = [*identity.aliases, team.name]
            identity.save(update_fields=['aliases'])
        team.identity = identity
        team.save(update_fields=['public_id', 'identity'])

    for race in Race.objects.order_by('slug', '-year', 'id').iterator():
        series_slug = race.slug
        race_format = 'stage_race' if race.is_stage_race else 'one_day'
        scope = 'regular'
        if race.classification == 'WC':
            scope = 'world_championship'
        elif race.classification == 'CC':
            scope = 'continental_championship'
        elif race.classification == 'NC':
            scope = 'national_championship'
        elif race.classification == 'OG':
            scope = 'olympic'
        series, _ = RaceSeries.objects.get_or_create(
            canonical_slug=series_slug,
            defaults={
                'current_name': race.name,
                'gender_category': race.category,
                'format': race_format,
                'scope': scope,
                'primary_country': race.country,
                'aliases': [race.name] if race.name else [],
            },
        )
        if race.name and race.name not in (series.aliases or []):
            series.aliases = [*series.aliases, race.name]
            series.save(update_fields=['aliases'])
        RaceSeriesAlias.objects.get_or_create(
            series=series,
            normalized_name=_normalize(race.name),
            valid_from_year=None,
            valid_to_year=None,
            locale='und',
            defaults={'name': race.name},
        )
        race.public_id = uuid.uuid4()
        race.series = series
        race.official_name = race.official_name or race.name
        race.host_country = race.host_country or race.country
        race.status = race.status or 'unknown'
        race.save(update_fields=['public_id', 'series', 'official_name', 'host_country', 'status'])

    for stage in Stage.objects.all().iterator():
        stage.public_id = uuid.uuid4()
        stage.stage_key = stage.stage_key or _stage_key(stage.number)
        stage.display_label = stage.display_label or f'Étape {stage.number}'
        if stage.stage_type in {'itt', 'ttt', 'prologue'}:
            stage.stage_kind = stage.stage_type
        stage.save(update_fields=['public_id', 'stage_key', 'display_label', 'stage_kind'])

    for entry in StartListEntry.objects.all().iterator():
        entry.public_id = uuid.uuid4()
        entry.save(update_fields=['public_id'])

    for result in Result.objects.all().iterator():
        result.public_id = uuid.uuid4()
        if result.time and result.elapsed_time_ms is None:
            result.elapsed_time_ms = int(result.time.total_seconds() * 1000)
        result.raw_display_time = result.raw_display_time or result.time_gap or ''
        result.save(update_fields=['public_id', 'elapsed_time_ms', 'raw_display_time'])


def backwards(apps, schema_editor):
    # Additive migration: canonical backfill is intentionally retained on rollback.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0006_teamidentity_race_finish_location_race_host_country_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
