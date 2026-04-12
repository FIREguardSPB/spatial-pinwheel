import unittest
from types import SimpleNamespace

from core.ml.dataset import build_training_rows_from_entities
from core.ml.trainer import train_classifier


class MLDatasetTests(unittest.TestCase):
    def test_build_training_rows_from_entities(self):
        signals = [
            SimpleNamespace(
                id='sig1',
                instrument_id='TQBR:SBER',
                side='BUY',
                entry=100.0,
                sl=99.0,
                tp=102.0,
                size=10.0,
                created_ts=1710000000000,
                status='executed',
                meta={
                    'final_decision': 'TAKE',
                    'strategy_name': 'breakout',
                    'regime': 'trend',
                    'decision': {'score': 74},
                    'trace_id': 'trace_1',
                },
            ),
            SimpleNamespace(
                id='sig2',
                instrument_id='TQBR:GAZP',
                side='SELL',
                entry=200.0,
                sl=202.0,
                tp=196.0,
                size=5.0,
                created_ts=1710000600000,
                status='rejected',
                meta={
                    'final_decision': 'TAKE',
                    'strategy_name': 'mean_reversion',
                    'regime': 'range',
                    'decision': {'score': 58},
                    'trace_id': 'trace_2',
                },
            ),
        ]
        positions = [
            SimpleNamespace(
                opened_signal_id='sig1',
                trace_id='trace_1',
                qty=0.0,
                realized_pnl=150.0,
                opened_qty=10.0,
                opened_ts=1710000000000,
                updated_ts=1710003600000,
                entry_fee_est=1.0,
                total_fees_est=2.0,
                mfe_pct=2.1,
                mae_pct=-0.5,
            ),
        ]
        datasets = build_training_rows_from_entities(signals, positions)
        self.assertEqual(len(datasets['take_fill'].rows), 2)
        self.assertEqual(len(datasets['trade_outcome'].rows), 1)
        self.assertEqual(datasets['trade_outcome'].rows[0].label, 1)
        self.assertEqual(datasets['take_fill'].rows[0].features['strategy'], 'breakout')

    def test_trade_outcome_prefers_closed_logs(self):
        signals = [
            SimpleNamespace(
                id='sig1',
                instrument_id='TQBR:SBER',
                side='BUY',
                entry=100.0,
                sl=99.0,
                tp=102.0,
                size=10.0,
                created_ts=1710000000000,
                status='executed',
                meta={
                    'final_decision': 'TAKE',
                    'strategy_name': 'breakout',
                    'regime': 'trend',
                    'decision': {'score': 74},
                    'trace_id': 'trace_1',
                },
            ),
        ]
        close_logs = [
            SimpleNamespace(
                ts=1710003600000,
                payload={
                    'signal_id': 'sig1',
                    'trace_id': 'trace_1',
                    'instrument_id': 'TQBR:SBER',
                    'opened_ts': 1710000000000,
                    'closed_ts': 1710003600000,
                    'opened_qty': 10.0,
                    'qty': 10.0,
                    'net_pnl': -15.0,
                    'fees_est': 1.2,
                    'entry_fee_est': 0.5,
                    'exit_fee_est': 0.7,
                    'reason': 'SL',
                    'exit_diagnostics': {
                        'bars_held': 6,
                        'mfe_pct': 0.8,
                        'mae_pct': -1.1,
                        'hold_utilization_pct': 55.0,
                        'realized_rr_multiple': -0.7,
                        'fee_load_pct': 0.06,
                    },
                },
            )
        ]
        datasets = build_training_rows_from_entities(signals, positions=[], close_logs=close_logs)
        self.assertEqual(len(datasets['trade_outcome'].rows), 1)
        row = datasets['trade_outcome'].rows[0]
        self.assertEqual(row.label, 0)
        self.assertEqual(row.meta['close_reason'], 'SL')
        self.assertEqual(row.features['bars_held'], 6)
        self.assertEqual(datasets['trade_outcome'].stats['mapped_close_logs'], 1)

    def test_train_classifier_rare_class_fallback(self):
        rows = []
        for idx in range(20):
            rows.append(
                SimpleNamespace(
                    signal_id=f's{idx}',
                    instrument_id='TQBR:SBER',
                    target='take_fill',
                    label=0 if idx == 19 else 1,
                    features={
                        'instrument_id': 'TQBR:SBER',
                        'side': 'BUY',
                        'strategy': 'breakout',
                        'regime': 'trend',
                        'msk_hour': idx,
                        'entry_price': 100 + idx,
                    },
                    meta={},
                )
            )
        dataset = SimpleNamespace(target='take_fill', rows=rows)
        artifact = train_classifier(dataset, min_rows=20)
        self.assertEqual(artifact.metrics['validation_mode'], 'train_only_rare_class_fallback')
        self.assertEqual(artifact.metrics['rows_validation'], 0)


if __name__ == '__main__':
    unittest.main()
