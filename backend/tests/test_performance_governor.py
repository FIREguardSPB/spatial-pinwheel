import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.services.performance_governor import _learning_multipliers, _row_status, evaluate_signal_governor


class PerformanceGovernorTests(unittest.TestCase):
    def test_row_status_pass(self):
        settings = SimpleNamespace(
            performance_governor_min_closed_trades=3,
            performance_governor_max_execution_error_rate=0.35,
            performance_governor_min_take_fill_rate=0.20,
        )
        status = _row_status({
            'closed_trades': 4,
            'takes': 5,
            'profit_factor': 1.3,
            'expectancy_per_trade': 10.0,
            'win_rate': 55.0,
            'take_fill_rate': 0.6,
            'execution_error_rate': 0.0,
        }, settings)
        self.assertEqual(status, 'pass')

    def test_row_status_fail(self):
        settings = SimpleNamespace(
            performance_governor_min_closed_trades=3,
            performance_governor_max_execution_error_rate=0.35,
            performance_governor_min_take_fill_rate=0.20,
        )
        status = _row_status({
            'closed_trades': 4,
            'takes': 6,
            'profit_factor': 0.6,
            'expectancy_per_trade': -120.0,
            'win_rate': 30.0,
            'take_fill_rate': 0.1,
            'execution_error_rate': 0.5,
        }, settings)
        self.assertEqual(status, 'fail')

    def test_learning_multipliers_fail(self):
        settings = SimpleNamespace(
            performance_governor_pass_risk_multiplier=1.2,
            performance_governor_fail_risk_multiplier=0.6,
            performance_governor_threshold_bonus=6,
            performance_governor_threshold_penalty=10,
            performance_governor_execution_priority_boost=1.2,
            performance_governor_execution_priority_penalty=0.7,
            performance_governor_allocator_boost=1.15,
            performance_governor_allocator_penalty=0.8,
        )
        risk_mult, threshold_adj, exec_prio, alloc_prio = _learning_multipliers('fail', settings)
        self.assertEqual(threshold_adj, 10)
        self.assertLess(risk_mult, 1.0)
        self.assertLess(exec_prio, 1.0)
        self.assertLess(alloc_prio, 1.0)

    @patch('core.services.performance_governor.build_performance_governor')
    def test_evaluate_signal_governor_blocks_weak_slice(self, mocked_build):
        mocked_build.return_value = {
            'slice_rows': [
                {
                    'slice': 'breakout | trend',
                    'strategy': 'breakout',
                    'regime': 'trend',
                    'status': 'fail',
                    'risk_multiplier': 0.6,
                    'threshold_adjustment': 10,
                    'execution_priority': 0.7,
                    'allocator_priority_multiplier': 0.8,
                    'action': 'suppress',
                },
            ],
            'strategy_rows': [],
            'regime_rows': [],
            'whitelist_by_regime': {'trend': ['mean_reversion']},
        }
        settings = SimpleNamespace(
            performance_governor_enabled=True,
            performance_governor_strict_whitelist=True,
            performance_governor_fail_risk_multiplier=0.6,
            performance_governor_threshold_penalty=10,
            performance_governor_execution_priority_penalty=0.7,
            performance_governor_allocator_penalty=0.8,
        )
        result = evaluate_signal_governor(object(), settings, instrument_id='TQBR:SBER', strategy='breakout', regime='trend')
        self.assertTrue(result['suppressed'])
        self.assertFalse(result['allowed'])
        self.assertLess(result['risk_multiplier'], 1.0)
        self.assertGreater(result['threshold_adjustment'], 0)


if __name__ == '__main__':
    unittest.main()
