from __future__ import annotations

import unittest
import time
from types import SimpleNamespace
from unittest.mock import patch

from core.services.live_validation import build_live_trader_validation


class _FakeQuery:
    def __init__(self, items):
        self._items = list(items)

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._items)


class _FakeDB:
    def __init__(self, signals, positions, logs=None):
        self._signals = signals
        self._positions = positions
        self._logs = logs or []

    def query(self, model):
        name = getattr(model, '__name__', '')
        if name == 'Signal':
            return _FakeQuery(self._signals)
        if name == 'Position':
            return _FakeQuery(self._positions)
        if name == 'DecisionLog':
            return _FakeQuery(self._logs)
        return _FakeQuery([])


class LiveValidationTests(unittest.TestCase):
    @patch('core.services.live_validation.build_paper_audit')
    @patch('core.services.live_validation.build_metrics')
    def test_build_live_validation_reports_statuses(self, mock_metrics, mock_audit):
        mock_metrics.return_value = {
            'profit_factor': 1.42,
            'expectancy_per_trade': 150.0,
            'avg_loss_per_trade': -600.0,
            'max_drawdown_pct': 7.5,
            'win_rate': 52.0,
            'avg_realized_to_mfe_capture_ratio': 0.51,
            'execution_error_count': 0,
            'portfolio_concentration_pct': 24.0,
            'signals_count': 20,
            'trades_count': 12,
            'conversion_rate': 60.0,
            'total_pnl': 1800.0,
            'capital_reallocations_count': 2,
            'portfolio_optimizer_adjustments_count': 3,
        }
        mock_audit.return_value = {
            'summary': {
                'green_days': 6,
                'red_days': 2,
                'avg_portfolio_risk_multiplier': 0.88,
            },
            'exit_diagnostics': {
                'avg_mfe_pct': 1.8,
                'avg_mae_pct': -0.6,
                'avg_mfe_capture_ratio': 0.51,
                'avg_mae_recovery_ratio': 0.72,
                'avg_adverse_slippage_bps': 5.0,
            },
            'recommendations': [],
        }

        now_ms = int(time.time() * 1000)
        signals = [
            SimpleNamespace(id='s1', created_ts=now_ms - 35 * 24 * 60 * 60 * 1000, meta={'event_regime': {'regime': 'trend_up'}, 'strategy_name': 'breakout'}),
            SimpleNamespace(id='s2', created_ts=now_ms - 28 * 24 * 60 * 60 * 1000, meta={'event_regime': {'regime': 'trend_up'}, 'strategy_name': 'breakout'}),
            SimpleNamespace(id='s3', created_ts=now_ms - 21 * 24 * 60 * 60 * 1000, meta={'event_regime': {'regime': 'mean_revert'}, 'strategy_name': 'mean_reversion'}),
            SimpleNamespace(id='s4', created_ts=now_ms - 14 * 24 * 60 * 60 * 1000, meta={'event_regime': {'regime': 'mean_revert'}, 'strategy_name': 'mean_reversion'}),
            SimpleNamespace(id='s5', created_ts=now_ms - 7 * 24 * 60 * 60 * 1000, meta={'event_regime': {'regime': 'trend_up'}, 'strategy_name': 'breakout'}),
            SimpleNamespace(id='s6', created_ts=now_ms - 2 * 24 * 60 * 60 * 1000, meta={'event_regime': {'regime': 'trend_up'}, 'strategy_name': 'breakout'}),
        ]
        week = 7 * 24 * 60 * 60 * 1000
        positions = [
            SimpleNamespace(instrument_id='A', qty=0, updated_ts=now_ms - 35 * 24 * 60 * 60 * 1000, opened_ts=now_ms - 35 * 24 * 60 * 60 * 1000 - 1000, realized_pnl=500, opened_signal_id='s1', strategy='breakout'),
            SimpleNamespace(instrument_id='B', qty=0, updated_ts=now_ms - 28 * 24 * 60 * 60 * 1000, opened_ts=now_ms - 28 * 24 * 60 * 60 * 1000 - 1000, realized_pnl=400, opened_signal_id='s2', strategy='breakout'),
            SimpleNamespace(instrument_id='C', qty=0, updated_ts=now_ms - 21 * 24 * 60 * 60 * 1000, opened_ts=now_ms - 21 * 24 * 60 * 60 * 1000 - 1000, realized_pnl=-200, opened_signal_id='s3', strategy='mean_reversion'),
            SimpleNamespace(instrument_id='D', qty=0, updated_ts=now_ms - 14 * 24 * 60 * 60 * 1000, opened_ts=now_ms - 14 * 24 * 60 * 60 * 1000 - 1000, realized_pnl=350, opened_signal_id='s4', strategy='mean_reversion'),
            SimpleNamespace(instrument_id='E', qty=0, updated_ts=now_ms - 7 * 24 * 60 * 60 * 1000, opened_ts=now_ms - 7 * 24 * 60 * 60 * 1000 - 1000, realized_pnl=450, opened_signal_id='s5', strategy='breakout'),
            SimpleNamespace(instrument_id='F', qty=0, updated_ts=now_ms - 2 * 24 * 60 * 60 * 1000, opened_ts=now_ms - 2 * 24 * 60 * 60 * 1000 - 1000, realized_pnl=-100, opened_signal_id='s6', strategy='breakout'),
        ]

        report = build_live_trader_validation(_FakeDB(signals, positions), days=45, weeks=8)
        self.assertEqual(report['summary']['overall_status'], 'partial')
        self.assertTrue(any(item['key'] == 'profit_factor' for item in report['checklist']))
        self.assertGreaterEqual(len(report['weekly_rows']), 5)
        self.assertGreaterEqual(len(report['regime_rows']), 2)
        pf_item = next(item for item in report['checklist'] if item['key'] == 'profit_factor')
        self.assertEqual(pf_item['status'], 'partial')
        exec_item = next(item for item in report['checklist'] if item['key'] == 'execution_quality')
        self.assertEqual(exec_item['status'], 'pass')


if __name__ == '__main__':
    unittest.main()
