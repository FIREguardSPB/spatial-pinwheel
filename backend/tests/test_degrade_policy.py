import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.services.degrade_policy import _POLICY_CACHE, evaluate_degrade_policy


class DegradePolicyTests(unittest.TestCase):
    def setUp(self):
        _POLICY_CACHE['key'] = None
        _POLICY_CACHE['expires_at'] = 0.0
        _POLICY_CACHE['result'] = None
        _POLICY_CACHE['stale_expires_at'] = 0.0
        _POLICY_CACHE['computed_at'] = 0.0

    @patch('core.services.degrade_policy._build_metrics')
    def test_enters_degraded_state(self, mock_metrics):
        mock_metrics.return_value = {
            'execution_error_count': 5,
            'profit_factor': 0.9,
            'expectancy_per_trade': -60.0,
            'max_drawdown_pct': 1.2,
            'trades_count': 6,
            'total_pnl': -1000.0,
        }
        settings = SimpleNamespace(
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
        result = evaluate_degrade_policy(object(), settings)
        self.assertEqual(result.state, 'degraded')
        self.assertEqual(result.risk_multiplier_override, 0.5)
        self.assertEqual(result.threshold_penalty, 8)
        self.assertFalse(result.block_new_entries)

    @patch('core.services.degrade_policy._build_metrics')
    def test_enters_frozen_state(self, mock_metrics):
        mock_metrics.return_value = {
            'execution_error_count': 11,
            'profit_factor': 0.5,
            'expectancy_per_trade': -400.0,
            'max_drawdown_pct': 6.5,
            'trades_count': 10,
            'total_pnl': -9000.0,
        }
        settings = SimpleNamespace(
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
        result = evaluate_degrade_policy(object(), settings)
        self.assertEqual(result.state, 'frozen')
        self.assertTrue(result.block_new_entries)
        self.assertEqual(result.risk_multiplier_override, 0.0)


if __name__ == '__main__':
    unittest.main()
