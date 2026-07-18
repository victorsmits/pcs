from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from core import pcs_circuit, pcs_client
from live import tasks


class _Response:
    status_code = 403
    text = ''
    content = b''

    def raise_for_status(self):
        raise AssertionError('raise_for_status should not be called for 403')


@override_settings(
    PCS_REQUEST_DELAY=0,
    PCS_403_THRESHOLD=2,
    PCS_CIRCUIT_BACKOFFS=(60, 300, 900),
    PCS_CIRCUIT_JITTER=0,
    PCS_LEGACY_ENABLED=True,
)
class PCSCircuitBreakerTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        pcs_client.reset_session()

    def tearDown(self):
        cache.clear()
        pcs_client.reset_session()

    def test_403_does_not_retry_aggressively_and_opens_circuit_after_threshold(self):
        session = Mock()
        session.headers = {}
        session.get.return_value = _Response()

        with patch('core.pcs_client._get_session', return_value=session), patch('core.pcs_client.time.sleep'):
            with self.assertRaises(pcs_client.PCSAccessForbiddenError):
                pcs_client.fetch_text('https://www.procyclingstats.com/one', force=True, max_retries=3)
            self.assertEqual(session.get.call_count, 1)
            self.assertFalse(pcs_circuit.current_state().open)

            with self.assertRaises(pcs_client.PCSAccessForbiddenError):
                pcs_client.fetch_text('https://www.procyclingstats.com/two', force=True, max_retries=3)
            self.assertEqual(session.get.call_count, 2)

        state = pcs_circuit.current_state()
        self.assertTrue(state.open)
        self.assertEqual(state.failure_count, 2)
        self.assertGreater(state.retry_after, 0)

    def test_open_circuit_skips_poll_active_sessions(self):
        pcs_circuit.open_circuit(60, failures=2)

        result = tasks.poll_active_sessions()

        self.assertEqual(result['queued'], 0)
        self.assertEqual(result['reason'], 'pcs_circuit_open')
        self.assertTrue(result['retry_after'])

    def test_success_closes_circuit_and_resets_failures(self):
        pcs_circuit.open_circuit(60, failures=3)

        pcs_circuit.record_success('https://www.procyclingstats.com/')

        state = pcs_circuit.current_state()
        self.assertFalse(state.open)
        self.assertEqual(state.failure_count, 0)
        self.assertIsNone(state.retry_after)
