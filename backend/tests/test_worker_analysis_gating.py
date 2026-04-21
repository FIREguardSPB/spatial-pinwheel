import unittest
from unittest.mock import patch

from apps.worker.main import WorkerRuntimeState, _is_optional_worker_task, _run_symbol_profile_bootstrap_task


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

    async def test_symbol_profile_bootstrap_task_preserves_current_phase(self):
        await self.state.set_phase('bootstrap', 'Worker bootstrapping')

        with patch('apps.worker.main.ensure_symbol_profiles', return_value={'trained': 2, 'errors': []}):
            await _run_symbol_profile_bootstrap_task(
                self.state,
                [self.ticker],
                train_limit=1,
                timeframe='1m',
                source='test',
            )

        snapshot = await self.state.snapshot()
        self.assertEqual(snapshot['phase'], 'bootstrap')
        self.assertEqual(snapshot['message'], 'Worker bootstrapping')
        self.assertEqual(snapshot['symbol_profiles_bootstrap']['trained'], 2)

    async def test_symbol_profile_bootstrap_task_is_optional_for_supervisor(self):
        self.assertTrue(_is_optional_worker_task('worker-symbol-profile-bootstrap'))
        self.assertFalse(_is_optional_worker_task('worker-analysis'))


if __name__ == '__main__':
    unittest.main()
