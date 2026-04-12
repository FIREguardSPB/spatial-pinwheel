import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.services.degrade_policy import _POLICY_CACHE, build_policy_runtime_payload_ui_safe


class DegradePolicyUiSafeTests(unittest.TestCase):
    def setUp(self):
        _POLICY_CACHE['key'] = None
        _POLICY_CACHE['expires_at'] = 0.0
        _POLICY_CACHE['stale_expires_at'] = 0.0
        _POLICY_CACHE['computed_at'] = 0.0
        _POLICY_CACHE['result'] = None
        _POLICY_CACHE['last_error'] = None
        _POLICY_CACHE['last_error_at'] = 0.0
        _POLICY_CACHE['warming_started_at'] = 0.0

    def _settings(self):
        return SimpleNamespace(
            updated_ts=1,
            auto_degrade_enabled=True,
            auto_freeze_enabled=True,
            auto_policy_lookback_days=14,
            auto_degrade_max_execution_errors=4,
            auto_freeze_max_execution_errors=10,
            auto_degrade_min_profit_factor=0.95,
            auto_freeze_min_profit_factor=0.70,
            auto_degrade_min_expectancy=-50.0,
            auto_freeze_min_expectancy=-250.0,
            auto_degrade_drawdown_pct=2.5,
            auto_freeze_drawdown_pct=5.0,
            auto_degrade_risk_multiplier=0.55,
            auto_degrade_threshold_penalty=8,
            auto_freeze_new_entries=True,
        )

    @patch('core.services.degrade_policy._schedule_policy_cache_refresh')
    def test_returns_loading_payload_without_blocking_when_cache_empty(self, mock_schedule):
        payload = build_policy_runtime_payload_ui_safe(self._settings())
        self.assertEqual(payload['status'], 'loading')
        self.assertEqual(payload['state'], 'unknown')
        mock_schedule.assert_called_once()
        self.assertIn('thresholds', payload)


    @patch('core.services.degrade_policy._schedule_policy_cache_refresh')
    def test_returns_error_payload_when_warmup_times_out(self, mock_schedule):
        from core.services.degrade_policy import _POLICY_CACHE, _POLICY_MAX_WARMING_SEC
        _POLICY_CACHE['warming_started_at'] = 1.0
        with patch('core.services.degrade_policy.time.monotonic', return_value=1.0 + _POLICY_MAX_WARMING_SEC + 1.0):
            payload = build_policy_runtime_payload_ui_safe(self._settings())
        self.assertEqual(payload['status'], 'error')
        self.assertIn('timed out', payload['error'])
        mock_schedule.assert_called_once()

if __name__ == '__main__':
    unittest.main()
