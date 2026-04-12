import unittest
from types import SimpleNamespace

from core.services.signal_freshness import apply_signal_freshness, compute_signal_age


class TestSignalFreshness(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            signal_freshness_enabled=True,
            signal_freshness_grace_bars=1.0,
            signal_freshness_penalty_per_bar=6,
            signal_freshness_max_bars=3.0,
        )

    def test_compute_signal_age_in_execution_bars(self):
        age_sec, age_bars = compute_signal_age(
            analysis_ts=1_700_000_000_000,
            execution_ts=1_700_000_180_000,
            execution_timeframe='1m',
        )
        self.assertEqual(age_sec, 180)
        self.assertAlmostEqual(age_bars, 3.0, places=3)

    def test_fresh_signal_keeps_take(self):
        decision, score, meta = apply_signal_freshness(
            decision='TAKE',
            score=72,
            threshold=70,
            analysis_ts=1_700_000_000_000,
            execution_ts=1_700_000_050_000,
            execution_timeframe='1m',
            settings=self.settings,
        )
        self.assertEqual(decision, 'TAKE')
        self.assertEqual(score, 72)
        self.assertFalse(meta.blocked)
        self.assertFalse(meta.applied)

    def test_stale_signal_blocks_take(self):
        decision, score, meta = apply_signal_freshness(
            decision='TAKE',
            score=78,
            threshold=70,
            analysis_ts=1_700_000_000_000,
            execution_ts=1_700_000_260_000,
            execution_timeframe='1m',
            settings=self.settings,
        )
        self.assertEqual(decision, 'SKIP')
        self.assertTrue(meta.blocked)
        self.assertTrue(meta.applied)
        self.assertLess(score, 78)
        self.assertIn('stale signal blocked', meta.reason)


if __name__ == '__main__':
    unittest.main()
