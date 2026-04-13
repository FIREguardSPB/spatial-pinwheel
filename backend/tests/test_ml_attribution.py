import unittest
from types import SimpleNamespace

from core.ml.attribution import build_ml_attribution_report_from_entities


class MLAttributionTests(unittest.TestCase):
    def test_build_ml_attribution_report_from_entities(self):
        signals = [
            SimpleNamespace(
                id='sig_profit',
                instrument_id='TQBR:SBER',
                created_ts=1710000000000,
                status='executed',
                meta={
                    'trace_id': 'trace_profit',
                    'strategy_name': 'breakout',
                    'regime': 'trend',
                    'decision': {'decision': 'TAKE', 'score': 80},
                    'final_decision': 'TAKE',
                    'ml_overlay': {'reason': 'ml_boost', 'action': 'boost'},
                },
            ),
            SimpleNamespace(
                id='sig_veto',
                instrument_id='TQBR:GAZP',
                created_ts=1710000100000,
                status='skipped',
                meta={
                    'trace_id': 'trace_veto',
                    'strategy_name': 'mean_reversion',
                    'regime': 'range',
                    'decision': {'decision': 'TAKE', 'score': 71},
                    'final_decision': 'SKIP',
                    'ml_overlay': {'reason': 'ml_take_veto', 'suppress_take': True, 'action': 'veto'},
                },
            ),
            SimpleNamespace(
                id='sig_guardrail',
                instrument_id='TQBR:LKOH',
                created_ts=1710000200000,
                status='rejected',
                meta={
                    'trace_id': 'trace_guardrail',
                    'strategy_name': 'breakout',
                    'regime': 'trend',
                    'decision': {'decision': 'TAKE', 'score': 77},
                    'final_decision': 'TAKE',
                },
            ),
            SimpleNamespace(
                id='sig_pending',
                instrument_id='TQBR:VTBR',
                created_ts=1710000300000,
                status='approved',
                meta={
                    'trace_id': 'trace_pending',
                    'strategy_name': 'breakout',
                    'regime': 'trend',
                    'decision': {'decision': 'TAKE', 'score': 73},
                    'final_decision': 'TAKE',
                },
            ),
        ]
        decision_logs = [
            SimpleNamespace(
                type='trade_filled',
                ts=1710000050000,
                payload={'signal_id': 'sig_profit', 'trace_id': 'trace_profit'},
            ),
            SimpleNamespace(
                type='position_closed',
                ts=1710000400000,
                payload={'signal_id': 'sig_profit', 'trace_id': 'trace_profit', 'net_pnl': 12.5, 'reason': 'TP'},
            ),
            SimpleNamespace(
                type='execution_risk_block',
                ts=1710000250000,
                payload={'signal_id': 'sig_guardrail', 'trace_id': 'trace_guardrail', 'risk_reason': 'daily_limit'},
            ),
        ]

        payload = build_ml_attribution_report_from_entities(signals, decision_logs, limit=10)
        summary = payload['summary']

        self.assertEqual(summary['signal_generated'], 4)
        self.assertEqual(summary['take_candidate'], 4)
        self.assertEqual(summary['take_decided'], 3)
        self.assertEqual(summary['take_vetoed_by_ml'], 1)
        self.assertEqual(summary['take_blocked_by_guardrail'], 1)
        self.assertEqual(summary['take_not_filled'], 1)
        self.assertEqual(summary['trade_filled'], 1)
        self.assertEqual(summary['trade_closed_profit'], 1)
        self.assertEqual(payload['breakdowns']['guardrail_reason']['daily_limit'], 1)
        self.assertEqual(payload['breakdowns']['ml_reason']['ml_take_veto'], 1)
        self.assertEqual(payload['breakdowns']['close_reason']['TP'], 1)
        self.assertEqual(payload['recent_rows'][0]['signal_id'], 'sig_pending')


if __name__ == '__main__':
    unittest.main()
