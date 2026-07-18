from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Race, Rider, Stage, Team
from live.models import LiveSession
from live import tasks


@override_settings(PCS_LEGACY_ENABLED=False)
class NoProviderNetworkInViewsTests(TestCase):
    def setUp(self):
        self.rider = Rider.objects.create(slug='rider-one', name='Rider One')
        self.team = Team.objects.create(slug='team-one', year=2026, name='Team One')
        self.race = Race.objects.create(
            slug='race-one', year=2026, name='Race One', start_date='2026-07-18', end_date='2026-07-18'
        )
        self.stage = Stage.objects.create(race=self.race, number=1, name='Stage One')
        LiveSession.objects.create(stage=self.stage, is_active=True)

    def test_web_routes_do_not_call_legacy_pcs_client(self):
        urls = [
            reverse('catalog:search') + '?q=Race',
            reverse('catalog:race_detail', kwargs={'slug': self.race.slug, 'year': self.race.year}),
            reverse('catalog:stage_detail', kwargs={'slug': self.race.slug, 'year': self.race.year, 'number': 1}),
            reverse('catalog:rider_detail', kwargs={'slug': self.rider.slug}),
            reverse('catalog:team_detail', kwargs={'slug': self.team.slug, 'year': self.team.year}),
            reverse('catalog:startlist', kwargs={'slug': self.race.slug, 'year': self.race.year}),
            reverse('live_api:stage_live_data', kwargs={'slug': self.race.slug, 'year': self.race.year, 'number': 1}),
        ]
        with patch('core.pcs_client.fetch_text', side_effect=AssertionError('network forbidden')), \
             patch('core.pcs_client.fetch_bytes', side_effect=AssertionError('network forbidden')), \
             patch('core.pcs_client.get_soup', side_effect=AssertionError('network forbidden')):
            for url in urls:
                response = self.client.get(url)
                assert response.status_code < 500, url

    def test_legacy_tasks_are_disabled_by_default(self):
        assert tasks.discover_today()['reason'] == 'pcs_legacy_disabled'
        assert tasks.poll_active_sessions()['reason'] == 'pcs_legacy_disabled'
        assert tasks.poll_live_session(123)['reason'] == 'pcs_legacy_disabled'
