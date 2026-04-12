import unittest

from apps.worker.main import WorkerRuntimeState


class WorkerAnalysisGatingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.ticker = 'TQBR:SBER'
        self.state = WorkerRuntimeState(
            tickers=[self.ticker],
            last_signal_check={self.ticker: 0.0},
            last_poll_ts={self.ticker: 0.0},
        )

    async def test_skips_reanalysis_when_candle_did_not_change(self):
        candle = {
            'time': 100,
            'open': 10,
            'high': 12,
            'low': 9,
            'close': 11,
            'volume': 1000,
        }
        await self.state.remember_candle(self.ticker, candle)

        self.assertTrue(await self.state.should_analyze(self.ticker, now=10.0, signal_interval_sec=5.0))
        self.assertFalse(await self.state.should_analyze(self.ticker, now=20.0, signal_interval_sec=5.0))

    async def test_allows_reanalysis_only_after_changed_candle_and_interval(self):
        first = {
            'time': 100,
            'open': 10,
            'high': 12,
            'low': 9,
            'close': 11,
            'volume': 1000,
        }
        second = {
            'time': 100,
            'open': 10,
            'high': 12.5,
            'low': 9,
            'close': 11.6,
            'volume': 1200,
        }

        await self.state.remember_candle(self.ticker, first)
        self.assertTrue(await self.state.should_analyze(self.ticker, now=10.0, signal_interval_sec=5.0))

        await self.state.remember_candle(self.ticker, second)
        self.assertFalse(await self.state.should_analyze(self.ticker, now=12.0, signal_interval_sec=5.0))
        self.assertTrue(await self.state.should_analyze(self.ticker, now=16.0, signal_interval_sec=5.0))


if __name__ == '__main__':
    unittest.main()
