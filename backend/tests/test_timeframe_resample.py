from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.services.timeframe_engine import resample_candles


class TimeframeResampleTests(unittest.TestCase):
    def test_drops_incomplete_last_bucket(self):
        candles = [
            {'time': 1000 * 60_000, 'open': 10, 'high': 11, 'low': 9, 'close': 10.5, 'volume': 1},
            {'time': 1001 * 60_000, 'open': 10.5, 'high': 12, 'low': 10, 'close': 11, 'volume': 2},
            {'time': 1002 * 60_000, 'open': 11, 'high': 11.2, 'low': 10.8, 'close': 11.1, 'volume': 3},
            {'time': 1003 * 60_000, 'open': 11.1, 'high': 11.4, 'low': 10.9, 'close': 11.3, 'volume': 4},
            {'time': 1004 * 60_000, 'open': 11.3, 'high': 11.5, 'low': 11.0, 'close': 11.4, 'volume': 5},
            {'time': 1005 * 60_000, 'open': 11.4, 'high': 11.6, 'low': 11.2, 'close': 11.5, 'volume': 6},
            {'time': 1006 * 60_000, 'open': 11.5, 'high': 11.7, 'low': 11.3, 'close': 11.6, 'volume': 7},
        ]
        result = resample_candles(candles, '5m')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['open'], 10.0)
        self.assertEqual(result[0]['close'], 11.4)
        self.assertEqual(result[0]['volume'], 15)

    def test_session_anchor_uses_deterministic_session_floor(self):
        day1 = [
            {'time': 1743404400000, 'open': 100, 'high': 101, 'low': 99, 'close': 100.5, 'volume': 10},
            {'time': 1743404460000, 'open': 100.5, 'high': 102, 'low': 100, 'close': 101.0, 'volume': 20},
            {'time': 1743404520000, 'open': 101.0, 'high': 103, 'low': 100.8, 'close': 102.0, 'volume': 30},
        ]
        day2 = [
            {'time': 1743490800000, 'open': 200, 'high': 201, 'low': 199, 'close': 200.5, 'volume': 11},
            {'time': 1743490860000, 'open': 200.5, 'high': 202, 'low': 200, 'close': 201.0, 'volume': 22},
            {'time': 1743490920000, 'open': 201.0, 'high': 203, 'low': 200.8, 'close': 202.0, 'volume': 33},
        ]
        result = resample_candles(day1 + day2, '3m')
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['time'], 1743404340000)
        self.assertEqual(result[1]['time'], 1743490740000)
        self.assertEqual(result[0]['close'], 101.0)
        self.assertEqual(result[1]['close'], 201.0)


if __name__ == '__main__':
    unittest.main()
