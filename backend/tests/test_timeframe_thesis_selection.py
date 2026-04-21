import unittest
from unittest.mock import patch

from core.strategy.base import BaseStrategy
from core.services.timeframe_engine import build_higher_tf_continuation_thesis


class _DummyStrategy(BaseStrategy):
    def __init__(self, signal_map: dict[str, dict | None], lookback: int = 10):
        self.signal_map = dict(signal_map)
        self._lookback = lookback

    @property
    def name(self) -> str:
        return 'breakout'

    @property
    def lookback(self) -> int:
        return self._lookback

    def analyze(self, instrument_id: str, candles: list[dict]):
        tf = candles[0].get('_tf') if candles else '1m'
        payload = self.signal_map.get(tf)
        if not payload:
            return None
        out = dict(payload)
        out.setdefault('instrument_id', instrument_id)
        out.setdefault('side', 'BUY')
        out.setdefault('entry', 100.0)
        out.setdefault('sl', 99.0)
        out.setdefault('tp', 102.0)
        out.setdefault('meta', {'strategy': 'breakout_v2'})
        return out


class TimeframeThesisSelectionTests(unittest.TestCase):
    def test_selector_prefers_15m_thesis_when_regime_stack_allows_it(self):
        from apps.worker.processor_support import _run_strategy_timeframe_search

        strategy = _DummyStrategy(
            {
                '1m': {'r': 1.1},
                '5m': {'r': 1.15},
                '15m': {'r': 1.2},
            }
        )
        base_history = [{'_tf': '1m', 'time': i, 'open': 100, 'high': 101, 'low': 99, 'close': 100.5, 'volume': 1000} for i in range(40)]

        def _fake_resample(candles, tf):
            return [{'_tf': tf, 'time': i, 'open': 100, 'high': 101, 'low': 99, 'close': 100.5, 'volume': 1000} for i in range(20)]

        with patch('apps.worker.processor_support.resample_candles', side_effect=_fake_resample), \
             patch('apps.worker.processor_support.select_timeframe_stack_for_regime', return_value={
                 'market_regime_profile': 'trend_continuation',
                 'context_timeframe': '30m',
                 'thesis_timeframes': ['15m', '5m'],
                 'execution_timeframe': '1m',
                 'allows_1m_thesis_exception': False,
             }):
            signal, _history, meta = _run_strategy_timeframe_search(
                strategy,
                'TQBR:SBER',
                base_history,
                {'analysis_timeframe': '15m', 'confirmation_timeframe': '15m'},
                type('S', (), {'higher_timeframe': '15m'})(),
            )

        self.assertIsNotNone(signal)
        self.assertEqual(signal['meta']['analysis_timeframe'], '15m')
        self.assertEqual(meta['selected_timeframe'], '15m')
        self.assertEqual(signal['meta']['timeframe_selection_reason'], 'requested')
        self.assertIsNotNone(signal['meta'].get('higher_tf_thesis'))
        self.assertEqual(signal['meta']['higher_tf_thesis']['thesis_timeframe'], '15m')

    def test_1m_is_used_as_execution_fallback_when_higher_tfs_have_no_signal(self):
        from apps.worker.processor_support import _run_strategy_timeframe_search

        strategy = _DummyStrategy(
            {
                '1m': {'r': 1.05},
                '5m': None,
                '15m': None,
            }
        )
        base_history = [{'_tf': '1m', 'time': i, 'open': 100, 'high': 101, 'low': 99, 'close': 100.5, 'volume': 1000} for i in range(40)]

        def _fake_resample(candles, tf):
            return [{'_tf': tf, 'time': i, 'open': 100, 'high': 101, 'low': 99, 'close': 100.5, 'volume': 1000} for i in range(20)]

        with patch('apps.worker.processor_support.resample_candles', side_effect=_fake_resample):
            signal, _history, meta = _run_strategy_timeframe_search(
                strategy,
                'TQBR:SBER',
                base_history,
                {'analysis_timeframe': '15m', 'confirmation_timeframe': '15m'},
                type('S', (), {'higher_timeframe': '15m'})(),
            )

        self.assertIsNotNone(signal)
        self.assertEqual(signal['meta']['analysis_timeframe'], '1m')
        self.assertEqual(meta['selected_timeframe'], '1m')
        self.assertEqual(signal['meta']['timeframe_selection_reason'], 'execution_fallback')

    def test_1m_trigger_can_be_promoted_into_higher_tf_thesis_when_context_aligns(self):
        from apps.worker.processor_support import _run_strategy_timeframe_search

        strategy = _DummyStrategy(
            {
                '1m': {'r': 1.35},
                '5m': None,
                '15m': None,
            }
        )
        base_history = [{'_tf': '1m', 'time': i, 'open': 100, 'high': 101, 'low': 99, 'close': 100.5, 'volume': 1000} for i in range(40)]

        def _fake_resample(candles, tf):
            return [{'_tf': tf, 'time': i, 'open': 100, 'high': 101, 'low': 99, 'close': 100.5 + (0.2 if tf == '15m' else 0.0), 'volume': 1000} for i in range(20)]

        with patch('apps.worker.processor_support.resample_candles', side_effect=_fake_resample), \
             patch('apps.worker.processor_support.select_timeframe_stack_for_regime', return_value={
                 'market_regime_profile': 'trend_continuation',
                 'context_timeframe': '30m',
                 'thesis_timeframes': ['15m', '5m'],
                 'execution_timeframe': '1m',
                 'allows_1m_thesis_exception': False,
             }), \
             patch('apps.worker.processor_support.detect_trend', return_value=('up', 0.9)):
            signal, _history, meta = _run_strategy_timeframe_search(
                strategy,
                'TQBR:SBER',
                base_history,
                {'analysis_timeframe': '15m', 'confirmation_timeframe': '15m'},
                type('S', (), {'higher_timeframe': '15m'})(),
            )

        self.assertIsNotNone(signal)
        self.assertEqual(signal['meta']['thesis_timeframe'], '15m')
        self.assertEqual(signal['meta']['analysis_timeframe'], '1m')
        self.assertEqual(signal['meta']['timeframe_selection_reason'], 'context_promoted_thesis')
        self.assertEqual(meta['selected_timeframe'], '1m')
        self.assertIsNotNone(signal['meta'].get('higher_tf_thesis'))
        self.assertEqual(signal['meta']['higher_tf_thesis']['thesis_timeframe'], '15m')


class HigherTimeframeThesisBuilderTests(unittest.TestCase):
    def test_builds_trend_continuation_without_fresh_breakout(self):
        candles = []
        price = 100.0
        for i in range(20):
            price += 0.45
            candles.append({
                'time': i,
                'open': price - 0.35,
                'high': price + 0.45,
                'low': price - 0.55,
                'close': price,
                'volume': 1000,
            })
        candles[-1]['high'] = candles[-2]['high'] - 0.05
        candles[-1]['close'] = candles[-2]['high'] - 0.08

        thesis = build_higher_tf_continuation_thesis(candles, timeframe='15m')

        self.assertIsNotNone(thesis)
        self.assertEqual(thesis['side'], 'BUY')
        self.assertEqual(thesis['thesis_timeframe'], '15m')

    def test_builds_pullback_hold_continuation(self):
        closes = [100, 101, 102, 103, 104, 105, 106, 106.5, 107, 107.5, 108, 108.5, 109, 109.5, 110, 109.6, 109.4, 109.8, 110.4, 110.9]
        candles = []
        for i, close in enumerate(closes):
            candles.append({
                'time': i,
                'open': close - 0.3,
                'high': close + 0.5,
                'low': close - 0.6,
                'close': close,
                'volume': 1000,
            })

        thesis = build_higher_tf_continuation_thesis(candles, timeframe='5m')

        self.assertIsNotNone(thesis)
        self.assertEqual(thesis['side'], 'BUY')
        self.assertEqual(thesis['thesis_timeframe'], '5m')

    def test_builds_reclaim_after_failed_breakdown(self):
        closes = [110, 109.5, 109, 108.5, 108, 107.5, 107, 106.5, 106, 105.5, 105, 104.8, 104.5, 104.2, 103.8, 103.5, 102.9, 104.0, 105.1, 106.0]
        candles = []
        for i, close in enumerate(closes):
            low = close - 0.5
            high = close + 0.5
            if i == 16:
                low = 101.8
            if i >= 17:
                high = close + 0.8
            candles.append({
                'time': i,
                'open': close + 0.2,
                'high': high,
                'low': low,
                'close': close,
                'volume': 1000,
            })

        thesis = build_higher_tf_continuation_thesis(candles, timeframe='15m')

        self.assertIsNotNone(thesis)
        self.assertEqual(thesis['side'], 'BUY')


if __name__ == '__main__':
    unittest.main()
