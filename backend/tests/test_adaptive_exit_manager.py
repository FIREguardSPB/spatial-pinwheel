import unittest
from types import SimpleNamespace

from core.services.adaptive_exit import AdaptiveExitManager


class AdaptiveExitManagerTests(unittest.TestCase):
    def test_partial_close_suppressed_when_cooldown_active(self):
        mgr = AdaptiveExitManager(SimpleNamespace(
            adaptive_exit_enabled=True,
            adaptive_exit_extend_bars_limit=8,
            adaptive_exit_tighten_sl_pct=0.35,
            adaptive_exit_max_partial_closes=2,
        ))
        decision = mgr.evaluate(
            position_side='BUY',
            current_price=107.8,
            avg_price=100.0,
            sl=98.0,
            tp=110.0,
            bars_held=8,
            base_hold_bars=10,
            history=[{'close': 107.95}, {'close': 107.8}],
            adaptive_plan={'regime': 'balanced'},
            event_regime={'action': 'observe'},
            partial_closes_count=1,
            partial_close_cooldown_active=True,
        )
        self.assertIsNone(decision.partial_close_ratio)
        self.assertIn('cooldown', ' '.join(decision.notes or []))

    def test_partial_close_suppressed_after_max_partials(self):
        mgr = AdaptiveExitManager(SimpleNamespace(
            adaptive_exit_enabled=True,
            adaptive_exit_extend_bars_limit=8,
            adaptive_exit_tighten_sl_pct=0.35,
            adaptive_exit_max_partial_closes=1,
        ))
        decision = mgr.evaluate(
            position_side='BUY',
            current_price=108.0,
            avg_price=100.0,
            sl=98.0,
            tp=110.0,
            bars_held=8,
            base_hold_bars=10,
            history=[{'close': 108.05}, {'close': 108.0}],
            adaptive_plan={'regime': 'balanced'},
            event_regime={'action': 'observe'},
            partial_closes_count=1,
            partial_close_cooldown_active=False,
        )
        self.assertIsNone(decision.partial_close_ratio)
        self.assertIn('max partial closes', ' '.join(decision.notes or []))


if __name__ == '__main__':
    unittest.main()
