import unittest

from apps.backtest.engine import BacktestEngine


class AlwaysLongStrategy:
    name = 'always_long'
    lookback = 5

    def analyze(self, instrument_id, candles):
        price = float(candles[-1]['close'])
        return {
            'side': 'BUY',
            'entry': price,
            'sl': price - 1.0,
            'tp': price + 2.0,
            'size': 1.0,
            'r': 2.0,
        }


class AlwaysShortStrategy:
    name = 'always_short'
    lookback = 5

    def analyze(self, instrument_id, candles):
        price = float(candles[-1]['close'])
        return {
            'side': 'SELL',
            'entry': price,
            'sl': price + 1.0,
            'tp': price - 2.0,
            'size': 1.0,
            'r': 2.0,
        }


def _candles(n=420, start=100.0, step=0.25):
    out = []
    price = start
    for i in range(n):
        close = price + step
        out.append({
            'time': 1_700_000_000 + i * 60,
            'open': price,
            'high': close + 0.2,
            'low': price - 0.2,
            'close': close,
            'volume': 1000,
        })
        price = close
    return out


class TestBacktestWalkForward(unittest.TestCase):
    def test_walk_forward_selects_best_out_of_sample_strategy(self):
        candles = _candles()
        engine = BacktestEngine(strategy=AlwaysLongStrategy(), settings=None, use_decision_engine=False)
        wf = engine.run_walk_forward('TEST', candles, strategies=[AlwaysLongStrategy(), AlwaysShortStrategy()], folds=4)
        self.assertEqual(wf['best_strategy'], 'always_long')
        self.assertGreaterEqual(wf['fold_count'], 1)
        self.assertTrue(all(fold['selected_strategy'] == 'always_long' for fold in wf['folds']))
        self.assertTrue(all('out_of_sample' in fold for fold in wf['folds']))
        self.assertGreater(wf['strategy_rankings'][0]['avg_oos_score'], wf['strategy_rankings'][-1]['avg_oos_score'])


if __name__ == '__main__':
    unittest.main()
