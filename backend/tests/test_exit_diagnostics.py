import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.services.exit_diagnostics import build_exit_diagnostics, classify_edge_decay


class _Pos:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class ExitDiagnosticsTests(unittest.TestCase):
    def test_tp_close_builds_positive_quality(self):
        pos = _Pos(avg_price=100.0, sl=98.0, tp=106.0, opened_qty=10, qty=10, opened_ts=1_000)
        diag = build_exit_diagnostics(
            position=pos,
            requested_close_price=106.0,
            close_price=105.8,
            reason='TP',
            bars_held=4,
            hold_limit_bars=10,
            gross_realized=58.0,
            net_realized=56.0,
            entry_fee=1.0,
            exit_fee=1.0,
            closed_qty=10,
            now_ms=61_000,
        )
        self.assertEqual(diag['edge_decay_state'], 'fast_realization')
        self.assertGreater(diag['tp_capture_ratio'], 0.9)
        self.assertIn(diag['close_quality'], {'excellent', 'good'})

    def test_time_stop_classifies_as_decay(self):
        state = classify_edge_decay(reason='TIME_STOP (12/12 bars)', net_realized=-5.0, bars_held=12, hold_limit_bars=12)
        self.assertEqual(state, 'time_decay')

    def test_late_failure_classification(self):
        state = classify_edge_decay(reason='SL', net_realized=-10.0, bars_held=9, hold_limit_bars=10)
        self.assertEqual(state, 'late_failure')


    def test_exit_capture_grade_and_missed_value(self):
        pos = _Pos(avg_price=100.0, sl=97.0, tp=108.0, opened_qty=10, qty=10, opened_ts=1_000, mfe_total_pnl=90.0)
        diag = build_exit_diagnostics(
            position=pos,
            requested_close_price=104.5,
            close_price=104.2,
            reason='TIME_STOP (9/9 bars)',
            bars_held=9,
            hold_limit_bars=9,
            gross_realized=42.0,
            net_realized=40.0,
            entry_fee=1.0,
            exit_fee=1.0,
            closed_qty=10,
            now_ms=91_000,
        )
        self.assertEqual(diag['edge_decay_state'], 'time_decay')
        self.assertIn(diag['exit_capture_grade'], {'weak_capture', 'poor_capture', 'neutral_capture'})
        self.assertGreaterEqual(diag['missed_tp_value_rub'], 0.0)
        self.assertGreaterEqual(diag['missed_mfe_value_rub'], 0.0)


if __name__ == '__main__':
    unittest.main()
