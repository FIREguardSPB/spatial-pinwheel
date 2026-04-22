import unittest
from types import SimpleNamespace

from core.services.adaptive_exit import AdaptiveExitManager


class AdaptiveExitManagerTests(unittest.TestCase):
    def test_partial_close_suppressed_when_cooldown_active(self):
        mgr = AdaptiveExitManager(SimpleNamespace(
            adaptive_exit_enabled=True,
            adaptive_exit_extend_bars_limit=8,
            adaptive_exit_tighten_sl_pct=0.35,
            adaptive_exit_break_even_enabled=True,
            adaptive_exit_break_even_progress_pct=0.35,
            adaptive_exit_trailing_enabled=True,
            adaptive_exit_trailing_activation_progress_pct=0.55,
            adaptive_exit_trailing_lock_ratio=0.45,
            adaptive_exit_thesis_decay_enabled=True,
            adaptive_exit_thesis_decay_progress_pct=0.2,
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
            position_qty=10,
            total_fees_est=8.0,
            best_price_seen=108.0,
        )
        self.assertIsNone(decision.partial_close_ratio)
        self.assertIn('cooldown', ' '.join(decision.notes or []))

    def test_partial_close_suppressed_after_max_partials(self):
        mgr = AdaptiveExitManager(SimpleNamespace(
            adaptive_exit_enabled=True,
            adaptive_exit_extend_bars_limit=8,
            adaptive_exit_tighten_sl_pct=0.35,
            adaptive_exit_break_even_enabled=True,
            adaptive_exit_break_even_progress_pct=0.35,
            adaptive_exit_trailing_enabled=False,
            adaptive_exit_trailing_activation_progress_pct=0.55,
            adaptive_exit_trailing_lock_ratio=0.45,
            adaptive_exit_thesis_decay_enabled=True,
            adaptive_exit_thesis_decay_progress_pct=0.2,
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
            position_qty=10,
            total_fees_est=8.0,
            best_price_seen=108.1,
        )
        self.assertIsNone(decision.partial_close_ratio)
        self.assertIn('max partial closes', ' '.join(decision.notes or []))

    def test_break_even_tightens_stop_after_progress(self):
        mgr = AdaptiveExitManager(SimpleNamespace(
            adaptive_exit_enabled=True,
            adaptive_exit_extend_bars_limit=8,
            adaptive_exit_tighten_sl_pct=0.35,
            adaptive_exit_break_even_enabled=True,
            adaptive_exit_break_even_progress_pct=0.35,
            adaptive_exit_trailing_enabled=True,
            adaptive_exit_trailing_activation_progress_pct=0.55,
            adaptive_exit_trailing_lock_ratio=0.45,
            adaptive_exit_thesis_decay_enabled=True,
            adaptive_exit_thesis_decay_progress_pct=0.2,
            adaptive_exit_max_partial_closes=2,
        ))
        decision = mgr.evaluate(
            position_side='BUY',
            current_price=104.5,
            avg_price=100.0,
            sl=98.0,
            tp=110.0,
            bars_held=5,
            base_hold_bars=10,
            history=[{'close': 103.7}, {'close': 104.1}, {'close': 104.5}],
            adaptive_plan={'regime': 'trend'},
            event_regime={'action': 'observe'},
            partial_closes_count=0,
            partial_close_cooldown_active=False,
            position_qty=10,
            total_fees_est=8.0,
            best_price_seen=104.6,
        )
        self.assertIsNotNone(decision.tighten_sl)
        self.assertGreater(decision.tighten_sl, 100.0)
        self.assertIn('break-even', ' '.join(decision.notes or []))

    def test_break_even_does_not_trigger_before_progress_threshold(self):
        mgr = AdaptiveExitManager(SimpleNamespace(
            adaptive_exit_enabled=True,
            adaptive_exit_extend_bars_limit=8,
            adaptive_exit_tighten_sl_pct=0.35,
            adaptive_exit_break_even_enabled=True,
            adaptive_exit_break_even_progress_pct=0.6,
            adaptive_exit_trailing_enabled=True,
            adaptive_exit_trailing_activation_progress_pct=0.55,
            adaptive_exit_trailing_lock_ratio=0.45,
            adaptive_exit_thesis_decay_enabled=True,
            adaptive_exit_thesis_decay_progress_pct=0.2,
            adaptive_exit_max_partial_closes=2,
        ))
        decision = mgr.evaluate(
            position_side='BUY',
            current_price=100.15,
            avg_price=100.0,
            sl=98.0,
            tp=110.0,
            bars_held=4,
            base_hold_bars=10,
            history=[{'close': 100.05}, {'close': 100.1}, {'close': 100.15}],
            adaptive_plan={'regime': 'balanced'},
            event_regime={'action': 'observe'},
            partial_closes_count=0,
            partial_close_cooldown_active=False,
            position_qty=10,
            total_fees_est=8.0,
            best_price_seen=100.2,
        )
        self.assertIsNone(decision.tighten_sl)

    def test_trailing_tightens_stop_for_winner(self):
        mgr = AdaptiveExitManager(SimpleNamespace(
            adaptive_exit_enabled=True,
            adaptive_exit_extend_bars_limit=8,
            adaptive_exit_tighten_sl_pct=0.35,
            adaptive_exit_break_even_enabled=True,
            adaptive_exit_break_even_progress_pct=0.2,
            adaptive_exit_trailing_enabled=True,
            adaptive_exit_trailing_activation_progress_pct=0.55,
            adaptive_exit_trailing_lock_ratio=0.45,
            adaptive_exit_thesis_decay_enabled=True,
            adaptive_exit_thesis_decay_progress_pct=0.2,
            adaptive_exit_max_partial_closes=2,
        ))
        decision = mgr.evaluate(
            position_side='BUY',
            current_price=107.0,
            avg_price=100.0,
            sl=100.2,
            tp=110.0,
            bars_held=7,
            base_hold_bars=10,
            history=[{'close': 105.8}, {'close': 106.4}, {'close': 107.0}],
            adaptive_plan={'regime': 'trend'},
            event_regime={'action': 'observe'},
            partial_closes_count=0,
            partial_close_cooldown_active=False,
            position_qty=10,
            total_fees_est=8.0,
            best_price_seen=108.0,
        )
        self.assertIsNotNone(decision.tighten_sl)
        self.assertGreater(decision.tighten_sl, 103.0)
        self.assertIn('trail winner', ' '.join(decision.notes or []))

    def test_healthy_winner_preserves_hold_before_decay_logic(self):
        mgr = AdaptiveExitManager(SimpleNamespace(
            adaptive_exit_enabled=True,
            adaptive_exit_extend_bars_limit=8,
            adaptive_exit_tighten_sl_pct=0.35,
            adaptive_exit_break_even_enabled=True,
            adaptive_exit_break_even_progress_pct=0.2,
            adaptive_exit_trailing_enabled=True,
            adaptive_exit_trailing_activation_progress_pct=0.55,
            adaptive_exit_trailing_lock_ratio=0.45,
            adaptive_exit_thesis_decay_enabled=True,
            adaptive_exit_thesis_decay_progress_pct=0.2,
            adaptive_exit_max_partial_closes=2,
        ))
        decision = mgr.evaluate(
            position_side='BUY',
            current_price=103.0,
            avg_price=100.0,
            sl=98.0,
            tp=110.0,
            bars_held=3,
            base_hold_bars=10,
            history=[{'close': 102.7}, {'close': 102.9}, {'close': 103.0}],
            adaptive_plan={'regime': 'trend'},
            event_regime={'action': 'observe'},
            partial_closes_count=0,
            partial_close_cooldown_active=False,
            position_qty=10,
            total_fees_est=8.0,
            best_price_seen=103.2,
        )
        self.assertGreater(decision.extend_hold_bars or 0, 10)
        self.assertIsNotNone(decision.tighten_sl)
        self.assertIn('healthy winner preserves hold', ' '.join(decision.notes or []))

    def test_trailing_does_not_loosen_existing_stop(self):
        mgr = AdaptiveExitManager(SimpleNamespace(
            adaptive_exit_enabled=True,
            adaptive_exit_extend_bars_limit=8,
            adaptive_exit_tighten_sl_pct=0.35,
            adaptive_exit_break_even_enabled=True,
            adaptive_exit_break_even_progress_pct=0.2,
            adaptive_exit_trailing_enabled=True,
            adaptive_exit_trailing_activation_progress_pct=0.55,
            adaptive_exit_trailing_lock_ratio=0.45,
            adaptive_exit_thesis_decay_enabled=True,
            adaptive_exit_thesis_decay_progress_pct=0.2,
            adaptive_exit_max_partial_closes=2,
        ))
        decision = mgr.evaluate(
            position_side='BUY',
            current_price=107.0,
            avg_price=100.0,
            sl=105.2,
            tp=110.0,
            bars_held=7,
            base_hold_bars=10,
            history=[{'close': 105.9}, {'close': 106.5}, {'close': 107.0}],
            adaptive_plan={'regime': 'trend'},
            event_regime={'action': 'observe'},
            partial_closes_count=0,
            partial_close_cooldown_active=False,
            position_qty=10,
            total_fees_est=8.0,
            best_price_seen=108.0,
        )
        self.assertTrue(decision.tighten_sl is None or decision.tighten_sl >= 105.2)

    def test_thesis_decay_exits_stalled_trade_before_time_stop(self):
        mgr = AdaptiveExitManager(SimpleNamespace(
            adaptive_exit_enabled=True,
            adaptive_exit_extend_bars_limit=8,
            adaptive_exit_tighten_sl_pct=0.35,
            adaptive_exit_break_even_enabled=True,
            adaptive_exit_break_even_progress_pct=0.35,
            adaptive_exit_trailing_enabled=True,
            adaptive_exit_trailing_activation_progress_pct=0.55,
            adaptive_exit_trailing_lock_ratio=0.45,
            adaptive_exit_thesis_decay_enabled=True,
            adaptive_exit_thesis_decay_progress_pct=0.2,
            adaptive_exit_max_partial_closes=2,
        ))
        decision = mgr.evaluate(
            position_side='BUY',
            current_price=100.6,
            avg_price=100.0,
            sl=98.0,
            tp=110.0,
            bars_held=5,
            base_hold_bars=10,
            history=[{'close': 101.1}, {'close': 100.9}, {'close': 100.7}, {'close': 100.6}],
            adaptive_plan={'regime': 'balanced'},
            event_regime={'action': 'observe'},
            partial_closes_count=0,
            partial_close_cooldown_active=False,
            position_qty=10,
            total_fees_est=8.0,
            best_price_seen=101.4,
        )
        self.assertEqual(decision.force_reason, 'THESIS_DECAY')
        self.assertIn('thesis decayed', ' '.join(decision.notes or []))

    def test_a_plus_conviction_delays_break_even_transition(self):
        mgr = AdaptiveExitManager(SimpleNamespace(
            adaptive_exit_enabled=True,
            adaptive_exit_extend_bars_limit=8,
            adaptive_exit_tighten_sl_pct=0.35,
            adaptive_exit_break_even_enabled=True,
            adaptive_exit_break_even_progress_pct=0.35,
            adaptive_exit_trailing_enabled=True,
            adaptive_exit_trailing_activation_progress_pct=0.55,
            adaptive_exit_trailing_lock_ratio=0.45,
            adaptive_exit_thesis_decay_enabled=True,
            adaptive_exit_thesis_decay_progress_pct=0.2,
            adaptive_exit_max_partial_closes=2,
        ))
        decision = mgr.evaluate(
            position_side='BUY',
            current_price=103.9,
            avg_price=100.0,
            sl=98.0,
            tp=110.0,
            bars_held=5,
            base_hold_bars=10,
            history=[{'close': 103.4}, {'close': 103.7}, {'close': 103.9}],
            adaptive_plan={'regime': 'trend'},
            event_regime={'action': 'observe'},
            partial_closes_count=0,
            partial_close_cooldown_active=False,
            position_qty=10,
            total_fees_est=8.0,
            best_price_seen=104.0,
            conviction_profile={'tier': 'A+'},
        )
        self.assertIsNotNone(decision.tighten_sl)
        self.assertNotIn('break-even', ' '.join(decision.notes or []))

    def test_c_conviction_moves_to_break_even_earlier(self):
        mgr = AdaptiveExitManager(SimpleNamespace(
            adaptive_exit_enabled=True,
            adaptive_exit_extend_bars_limit=8,
            adaptive_exit_tighten_sl_pct=0.35,
            adaptive_exit_break_even_enabled=True,
            adaptive_exit_break_even_progress_pct=0.35,
            adaptive_exit_trailing_enabled=True,
            adaptive_exit_trailing_activation_progress_pct=0.55,
            adaptive_exit_trailing_lock_ratio=0.45,
            adaptive_exit_thesis_decay_enabled=True,
            adaptive_exit_thesis_decay_progress_pct=0.2,
            adaptive_exit_max_partial_closes=2,
        ))
        decision = mgr.evaluate(
            position_side='BUY',
            current_price=103.1,
            avg_price=100.0,
            sl=98.0,
            tp=110.0,
            bars_held=5,
            base_hold_bars=10,
            history=[{'close': 102.4}, {'close': 102.8}, {'close': 103.1}],
            adaptive_plan={'regime': 'balanced'},
            event_regime={'action': 'observe'},
            partial_closes_count=0,
            partial_close_cooldown_active=False,
            position_qty=10,
            total_fees_est=8.0,
            best_price_seen=103.2,
            conviction_profile={'tier': 'C'},
        )
        self.assertIsNotNone(decision.tighten_sl)
        self.assertIn('break-even', ' '.join(decision.notes or []))

    def test_higher_timeframe_alignment_makes_trade_more_patient(self):
        mgr = AdaptiveExitManager(SimpleNamespace(
            adaptive_exit_enabled=True,
            adaptive_exit_extend_bars_limit=8,
            adaptive_exit_tighten_sl_pct=0.35,
            adaptive_exit_break_even_enabled=True,
            adaptive_exit_break_even_progress_pct=0.35,
            adaptive_exit_trailing_enabled=True,
            adaptive_exit_trailing_activation_progress_pct=0.55,
            adaptive_exit_trailing_lock_ratio=0.45,
            adaptive_exit_thesis_decay_enabled=True,
            adaptive_exit_thesis_decay_progress_pct=0.2,
            adaptive_exit_max_partial_closes=2,
        ))
        aligned = mgr.evaluate(
            position_side='BUY',
            current_price=103.1,
            avg_price=100.0,
            sl=98.0,
            tp=110.0,
            bars_held=5,
            base_hold_bars=10,
            history=[{'close': 102.7}, {'close': 102.9}, {'close': 103.1}],
            adaptive_plan={'regime': 'trend', 'higher_timeframe_trend': 'up'},
            event_regime={'action': 'observe'},
            partial_closes_count=0,
            partial_close_cooldown_active=False,
            position_qty=10,
            total_fees_est=8.0,
            best_price_seen=103.2,
            conviction_profile={'tier': 'B', 'higher_timeframe_trend': 'up'},
        )
        counter = mgr.evaluate(
            position_side='BUY',
            current_price=103.1,
            avg_price=100.0,
            sl=98.0,
            tp=110.0,
            bars_held=5,
            base_hold_bars=10,
            history=[{'close': 102.7}, {'close': 102.9}, {'close': 103.1}],
            adaptive_plan={'regime': 'trend', 'higher_timeframe_trend': 'down'},
            event_regime={'action': 'observe'},
            partial_closes_count=0,
            partial_close_cooldown_active=False,
            position_qty=10,
            total_fees_est=8.0,
            best_price_seen=103.2,
            conviction_profile={'tier': 'B', 'higher_timeframe_trend': 'down'},
        )
        aligned_sl = aligned.tighten_sl or 0.0
        counter_sl = counter.tighten_sl or 0.0
        self.assertLessEqual(aligned_sl, counter_sl)



if __name__ == '__main__':
    unittest.main()
