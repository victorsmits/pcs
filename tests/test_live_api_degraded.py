from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Race, Stage


@override_settings(PCS_LEGACY_ENABLED=False, ALLOWED_HOSTS=['testserver'])
class LiveApiDegradedTests(TestCase):
    def test_missing_stage_returns_degraded_payload_without_404(self):
        Race.objects.create(slug='tour-de-france', year=2026, name='Tour de France')

        response = self.client.get(reverse(
            'live_api:stage_live_data',
            kwargs={'slug': 'tour-de-france', 'year': 2026, 'number': 14},
        ))

        assert response.status_code == 200
        payload = response.json()
        assert payload['available'] is False
        assert payload['reason'] == 'stage_not_available_locally'
        assert payload['race'] == 'Tour de France'

    def test_missing_live_session_returns_degraded_payload_without_404(self):
        race = Race.objects.create(slug='tour-de-france', year=2026, name='Tour de France')
        Stage.objects.create(race=race, number=14)

        response = self.client.get(reverse(
            'live_api:stage_live_data',
            kwargs={'slug': 'tour-de-france', 'year': 2026, 'number': 14},
        ))

        assert response.status_code == 200
        payload = response.json()
        assert payload['available'] is False
        assert payload['reason'] == 'live_session_not_available_locally'
        assert payload['race'] == 'Tour de France'
