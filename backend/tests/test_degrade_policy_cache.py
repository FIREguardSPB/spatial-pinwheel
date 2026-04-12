import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.services.degrade_policy import _POLICY_CACHE, build_policy_runtime_payload, evaluate_degrade_policy


class DegradePolicyCacheTests(unittest.TestCase):
    def setUp(self):
        _POLICY_CACHE["key"] = None
        _POLICY_CACHE["expires_at"] = 0.0
        _POLICY_CACHE["result"] = None
        _POLICY_CACHE["stale_expires_at"] = 0.0
        _POLICY_CACHE["computed_at"] = 0.0

    def _settings(self):
        return SimpleNamespace(
            updated_ts=123456789,
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
            auto_degrade_risk_multiplier=0.5,
            auto_degrade_threshold_penalty=8,
            auto_freeze_new_entries=True,
        )

    @patch('core.services.degrade_policy._build_freeze_analytics')
    @patch('core.services.degrade_policy._build_metrics')
    def test_evaluate_policy_uses_short_ttl_cache(self, mock_metrics, mock_freeze):
        mock_metrics.return_value = {
            'execution_error_count': 1,
            'profit_factor': 1.1,
            'expectancy_per_trade': 15.0,
            'max_drawdown_pct': 0.5,
            'trades_count': 6,
            'total_pnl': 1200.0,
        }
        mock_freeze.return_value = {'execution_error_streak': 0, 'rejection_streak': 0, 'recent_execution_errors': []}
        settings = self._settings()

        first = evaluate_degrade_policy(object(), settings)
        second = evaluate_degrade_policy(object(), settings)

        self.assertEqual(first.state, 'normal')
        self.assertEqual(second.state, 'normal')
        self.assertEqual(mock_metrics.call_count, 1)
        self.assertEqual(mock_freeze.call_count, 1)

    @patch('core.services.degrade_policy.evaluate_degrade_policy', side_effect=RuntimeError('boom'))
    def test_runtime_payload_falls_back_to_error_payload(self, _mock_eval):
        payload = build_policy_runtime_payload(object(), self._settings())
        self.assertEqual(payload['state'], 'unknown')
        self.assertIn(payload['status'], {'error', 'stale-cache'})
        self.assertTrue(payload['enabled'])


if __name__ == '__main__':
    unittest.main()
