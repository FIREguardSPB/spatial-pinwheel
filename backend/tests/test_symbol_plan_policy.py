from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class SymbolPlanPolicyTests(unittest.TestCase):
    def test_selected_strategy_respects_global_whitelist(self):
        try:
            from core.services import symbol_adaptive
        except Exception as exc:  # pragma: no cover - env dependent
            self.skipTest(f'symbol_adaptive import unavailable in this env: {exc}')
            return

        settings = SimpleNamespace(
            decision_threshold=30,
            time_stop_bars=12,
            signal_reentry_cooldown_sec=60,
            strategy_name='breakout',
            higher_timeframe='15m',
            trade_mode='auto_paper',
        )
        candles = [
            {'time': 1, 'open': 100, 'high': 101, 'low': 99, 'close': 100, 'volume': 10},
            {'time': 2, 'open': 100, 'high': 102, 'low': 99, 'close': 101, 'volume': 11},
            {'time': 3, 'open': 101, 'high': 103, 'low': 100, 'close': 102, 'volume': 12},
        ]
        fake_profile = {
            'preferred_strategies': 'mean_reversion,vwap_bounce',
            'decision_threshold_offset': 0,
            'hold_bars_base': 12,
            'hold_bars_min': 4,
            'hold_bars_max': 30,
            'reentry_cooldown_sec': 60,
            'risk_multiplier': 1.0,
            'aggressiveness': 1.0,
            'autotune': False,
            'profile_version': 2,
            'updated_ts': 123,
            'last_tuned_ts': 0,
        }
        perf = {'sample_size': 0, 'win_rate': None, 'avg_bars': None, 'avg_win_bars': None, 'avg_loss_bars': None, 'avg_pnl': None, 'best_strategy': 'mean_reversion'}
        features = {'regime': 'compression', 'volatility_pct': 0.1, 'trend_strength': 0.2, 'chop_ratio': 0.8, 'body_ratio': 0.2}

        with patch.object(symbol_adaptive, '_resolve_profile_payload', return_value=fake_profile), \
             patch.object(symbol_adaptive, '_recent_performance', return_value=perf), \
             patch.object(symbol_adaptive, '_recent_event_regime', return_value=None), \
             patch.object(symbol_adaptive, '_extract_features', return_value=features):
            plan = symbol_adaptive.build_symbol_plan(None, 'TQBR:SBER', candles, settings, persist=False)

        self.assertEqual(plan.strategy_name, 'breakout')
        self.assertIn('profile strategies constrained by global whitelist', plan.notes or [])


if __name__ == '__main__':
    unittest.main()
