"""
P5 Tests — Indicators (P5-01): Bollinger Bands, Stochastic, VWAP, VolumeRatio.
Все тесты проверяют математически ожидаемые значения.
"""
import math
import unittest
from apps.worker.decision_engine.indicators import (
    calc_bollinger, calc_stochastic, calc_vwap, calc_volume_ratio,
    calc_ema, calc_rsi, calc_atr,
)


def _flat(n=30, price=100.0):
    """n candles all at the same price."""
    return [price] * n


def _up(n=50, start=90.0, step=1.0):
    return [start + i * step for i in range(n)]


def _candles(closes, vol=1000.0):
    return [{"high": c+1, "low": c-1, "close": c, "volume": vol} for c in closes]


class TestBollingerBands(unittest.TestCase):

    def test_flat_price_narrow_bands(self):
        """Flat price → σ = 0 → upper == middle == lower."""
        closes = _flat(30, 100.0)
        result = calc_bollinger(closes, period=20)
        self.assertIsNotNone(result)
        upper, middle, lower = result
        self.assertAlmostEqual(middle, 100.0, places=4)
        self.assertAlmostEqual(upper, lower, places=4)

    def test_middle_is_sma(self):
        """Middle band = SMA of last 20 prices."""
        closes = list(range(1, 31))   # 1..30
        upper, middle, lower = calc_bollinger(closes, period=20)
        expected_sma = sum(range(11, 31)) / 20   # last 20
        self.assertAlmostEqual(middle, expected_sma, places=3)

    def test_upper_lower_symmetric(self):
        """upper - middle == middle - lower for any input."""
        import random
        random.seed(42)
        closes = [100 + random.gauss(0, 5) for _ in range(40)]
        upper, middle, lower = calc_bollinger(closes, period=20)
        self.assertAlmostEqual(upper - middle, middle - lower, places=5)

    def test_rising_prices_upper_above_current(self):
        """Rising sequence → upper > last close."""
        closes = _up(30)
        upper, _, lower = calc_bollinger(closes, period=20)
        self.assertGreater(upper, closes[-1])
        self.assertLess(lower, closes[-1])

    def test_returns_none_insufficient_data(self):
        self.assertIsNone(calc_bollinger([1.0, 2.0], period=20))

    def test_std_dev_2_wider_than_1(self):
        import random; random.seed(7)
        closes = [100 + random.gauss(0, 3) for _ in range(30)]
        u1, m1, l1 = calc_bollinger(closes, period=20, std_dev=1.0)
        u2, m2, l2 = calc_bollinger(closes, period=20, std_dev=2.0)
        self.assertGreater(u2 - l2, u1 - l1)


class TestStochastic(unittest.TestCase):

    def test_monotonic_up_near_100(self):
        """Monotonically rising → %K near 100."""
        closes = _up(30)
        highs  = [c + 1 for c in closes]
        lows   = [c - 1 for c in closes]
        result = calc_stochastic(highs, lows, closes, k_period=14, d_period=3)
        self.assertIsNotNone(result)
        k, d = result
        self.assertGreater(k, 80)

    def test_monotonic_down_near_0(self):
        """Monotonically falling → %K near 0."""
        closes = list(reversed(_up(30)))
        highs  = [c + 1 for c in closes]
        lows   = [c - 1 for c in closes]
        k, d = calc_stochastic(highs, lows, closes)
        self.assertLess(k, 20)

    def test_range_0_to_100(self):
        """Both %K and %D always in [0, 100]."""
        import random; random.seed(13)
        closes = [100 + random.uniform(-5, 5) for _ in range(40)]
        highs  = [c + abs(random.uniform(0, 3)) for c in closes]
        lows   = [c - abs(random.uniform(0, 3)) for c in closes]
        k, d = calc_stochastic(highs, lows, closes)
        self.assertGreaterEqual(k, 0)
        self.assertLessEqual(k, 100)
        self.assertGreaterEqual(d, 0)
        self.assertLessEqual(d, 100)

    def test_returns_none_insufficient(self):
        self.assertIsNone(calc_stochastic([1]*5, [0]*5, [0.5]*5, k_period=14, d_period=3))

    def test_flat_price_returns_50(self):
        """Flat H/L/C → no range → sentinel 50."""
        closes = _flat(25)
        highs = lows = closes[:]
        k, d = calc_stochastic(highs, lows, closes, k_period=14, d_period=3)
        self.assertAlmostEqual(k, 50.0, delta=1.0)


class TestVWAP(unittest.TestCase):

    def test_equal_volumes_equals_typical_price(self):
        """With equal volumes, VWAP = mean typical price."""
        closes = [10.0, 20.0, 30.0]
        highs  = [11.0, 21.0, 31.0]
        lows   = [9.0,  19.0, 29.0]
        vols   = [100.0, 100.0, 100.0]
        vwap = calc_vwap(highs, lows, closes, vols)
        expected = sum((h+l+c)/3 for h,l,c in zip(highs,lows,closes)) / 3
        self.assertAlmostEqual(vwap, expected, places=4)

    def test_higher_volume_shifts_vwap(self):
        """Higher volume on bar 2 pulls VWAP toward bar 2 price."""
        closes = [100.0, 200.0]
        highs  = [101.0, 201.0]
        lows   = [99.0,  199.0]
        vols   = [1.0,   9.0]   # bar 2 dominates
        vwap = calc_vwap(highs, lows, closes, vols)
        self.assertGreater(vwap, 150.0)   # closer to 200 than 100

    def test_returns_none_zero_volume(self):
        self.assertIsNone(calc_vwap([10.0], [9.0], [9.5], [0.0]))

    def test_single_bar(self):
        vwap = calc_vwap([11.0], [9.0], [10.0], [500.0])
        self.assertAlmostEqual(vwap, 10.0, places=4)   # (11+9+10)/3


class TestVolumeRatio(unittest.TestCase):

    def test_constant_volume_ratio_is_1(self):
        vols = [100.0] * 25
        ratio = calc_volume_ratio(vols, period=20)
        self.assertAlmostEqual(ratio, 1.0, places=3)

    def test_doubled_last_bar_ratio_is_2(self):
        vols = [100.0] * 21
        vols[-1] = 200.0
        ratio = calc_volume_ratio(vols, period=20)
        self.assertAlmostEqual(ratio, 2.0, places=3)

    def test_half_volume_ratio_is_0_5(self):
        vols = [100.0] * 21
        vols[-1] = 50.0
        ratio = calc_volume_ratio(vols, period=20)
        self.assertAlmostEqual(ratio, 0.5, places=3)

    def test_returns_none_insufficient(self):
        self.assertIsNone(calc_volume_ratio([100.0] * 5, period=20))

    def test_non_negative(self):
        import random; random.seed(99)
        vols = [abs(random.gauss(1000, 200)) + 1 for _ in range(30)]
        ratio = calc_volume_ratio(vols, period=20)
        self.assertGreater(ratio, 0)


if __name__ == "__main__":
    unittest.main()
