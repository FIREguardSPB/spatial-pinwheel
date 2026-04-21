import unittest
from types import SimpleNamespace


class ProcessorCorrelationMapTests(unittest.TestCase):
    def test_builds_candles_map_only_for_current_ticker_and_open_positions(self):
        from apps.worker.correlation_map import build_correlation_candles_map

        class _Aggregator:
            def __init__(self):
                self.calls = []
                self._history = {
                    'TQBR:SBER': [1],
                    'TQBR:GAZP': [1],
                    'TQBR:LKOH': [1],
                    'TQBR:MOEX': [1],
                }

            def get_history(self, ticker):
                self.calls.append(ticker)
                return [{'close': 100.0 + len(self.calls)}]

        class _Query:
            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return [SimpleNamespace(instrument_id='TQBR:GAZP'), SimpleNamespace(instrument_id='TQBR:LKOH')]

        class _DB:
            def query(self, _model):
                return _Query()

        aggregator = _Aggregator()
        result = build_correlation_candles_map(_DB(), aggregator, 'TQBR:SBER', [{'close': 101.0}])

        self.assertEqual(set(result.keys()), {'TQBR:SBER', 'TQBR:GAZP', 'TQBR:LKOH'})
        self.assertEqual(set(aggregator.calls), {'TQBR:GAZP', 'TQBR:LKOH'})
        self.assertNotIn('TQBR:MOEX', aggregator.calls)
