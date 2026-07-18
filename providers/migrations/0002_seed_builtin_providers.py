from django.db import migrations


def forwards(apps, schema_editor):
    Provider = apps.get_model('providers', 'Provider')
    Provider.objects.update_or_create(
        key='legacy-pcs',
        defaults={
            'name': 'Legacy ProCyclingStats mappings',
            'provider_type': 'legacy',
            'enabled': False,
            'base_url': '',
            'capabilities': [],
            'authority_level': 'legacy',
            'attribution_text': 'Historical local data originally associated with PCS identifiers.',
            'terms_url': '',
            'health_status': 'disabled',
        },
    )
    Provider.objects.update_or_create(
        key='manual',
        defaults={
            'name': 'Manual corrections',
            'provider_type': 'manual',
            'enabled': True,
            'capabilities': [],
            'authority_level': 'manual_override',
            'health_status': 'unknown',
        },
    )
    Provider.objects.update_or_create(
        key='seed',
        defaults={
            'name': 'Versioned seed files',
            'provider_type': 'fixture',
            'enabled': True,
            'capabilities': ['RACE_SERIES'],
            'authority_level': 'official',
            'health_status': 'unknown',
        },
    )


class Migration(migrations.Migration):
    dependencies = [('providers', '0001_initial')]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
