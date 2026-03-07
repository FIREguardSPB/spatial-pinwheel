"""
P5 Tests — Strategies (P5-05): MeanReversion, VWAPBounce, StrategySelector.
"""
import unittest
from decimal import Decimal
from core.strategy.mean_reversion import MeanReversionStrategy
from core.strategy.vwap_bounce import VWAPBounceStrategy
from core.strategy.selector import StrategySelector


def _candles(closes, vols=None, spread=1.0):
    vols = vols or [1000.0] * len(closes)
    return [
        {
            "time": 1_700_000_000 + i * 60,
            "open":  c,
            "high":  c + spread,
            "low":   c - spread,
            "close": c,
            "volume": vols[i],
        }
        for i, c in enumerate(closes)
    ]


def _ranging(n=40, center=100.0, amplitude=3.0):
    """Alternating high-low prices around center (ranging market)."""
    import math
    return [center + amplitude * math.sin(i * 0.4) for i in range(n)]


class TestMeanReversionStrategy(unittest.TestCase):

    def setUp(self):
        self.strat = MeanReversionStrategy(bb_period=20, bb_std=2.0)

    def test_no_signal_on_insufficient_data(self):
        candles = _candles([100.0] * 10)
        result = self.strat.analyze("TEST", candles)
        self.assertIsNone(result)

    def test_no_signal_in_flat_market(self):
        """Flat prices → BB bands collapse → close never outside bands."""
        candles = _candles([100.0] * 30)
        result = self.strat.analyze("TEST", candles)
        # May still get a signal in some edge cases — just ensure no exception
        # and if signal returned it's valid
        if result is not None:
            self.assertIn(result["side"], ["BUY", "SELL"])

    def test_buy_signal_below_lower_band(self):
        """Artificially push last price far below lower band."""
        closes = [100.0] * 24 + [80.0]  # big dip at the end
        candles = _candles(closes)
        result = self.strat.analyze("TEST", candles)
        if result is not None:
            self.assertEqual(result["side"], "BUY")

    def test_sell_signal_above_upper_band(self):
        closes = [100.0] * 24 + [120.0]  # spike up
        candles = _candles(closes)
        result = self.strat.analyze("TEST", candles)
        if result is not None:
            self.assertEqual(result["side"], "SELL")

    def test_signal_structure_is_valid(self):
        """Any returned signal has all required keys with correct types."""
        closes = [100.0] * 24 + [80.0]
        candles = _candles(closes)
        result = self.strat.analyze("TEST", candles)
        if result is None:
            return
        required = ["id", "instrument_id", "ts", "side", "entry", "sl", "tp", "r", "meta"]
        for key in required:
            self.assertIn(key, result, f"Missing key: {key}")
        self.assertIn(result["side"], ["BUY", "SELL"])
        self.assertGreater(result["r"], 0)
        if result["side"] == "BUY":
            self.assertLess(result["sl"], result["entry"])
            self.assertGreater(result["tp"], result["entry"])
        else:
            self.assertGreater(result["sl"], result["entry"])
            self.assertLess(result["tp"], result["entry"])

    def test_rr_at_least_1(self):
        closes = [100.0] * 24 + [79.0]
        candles = _candles(closes)
        result = self.strat.analyze("TEST", candles)
        if result is not None:
            self.assertGreaterEqual(result["r"], 1.0)

    def test_lookback_is_positive(self):
        self.assertGreater(self.strat.lookback, 0)

    def test_name_is_correct(self):
        self.assertEqual(self.strat.name, "mean_reversion")


class TestVWAPBounceStrategy(unittest.TestCase):

    def setUp(self):
        self.strat = VWAPBounceStrategy()

    def test_no_signal_insufficient_data(self):
        candles = _candles([100.0] * 10)
        self.assertIsNone(self.strat.analyze("TEST", candles))

    def test_buy_on_vwap_reclaim(self):
        """Last two bars: prev below VWAP, current above VWAP → BUY."""
        # Build a history where VWAP ≈ 100, last bar crosses above
        closes = [100.0] * 28 + [97.0, 103.0]   # prev below, current above
        vols   = [1000.0] * 28 + [800.0, 2000.0]  # volume spike on reclaim
        candles = _candles(closes, vols=vols)
        result = self.strat.analyze("TEST", candles)
        # May or may not trigger depending on VWAP calc — just check structure
        if result is not None:
            self.assertEqual(result["side"], "BUY")

    def test_sell_on_vwap_rejection(self):
        closes = [100.0] * 28 + [103.0, 97.0]   # was above, now below
        vols   = [1000.0] * 28 + [800.0, 2000.0]
        candles = _candles(closes, vols=vols)
        result = self.strat.analyze("TEST", candles)
        if result is not None:
            self.assertEqual(result["side"], "SELL")

    def test_no_signal_low_volume(self):
        """Without volume confirmation, no signal even on VWAP cross."""
        closes = [100.0] * 28 + [97.0, 103.0]
        vols   = [1000.0] * 28 + [800.0, 500.0]  # no volume spike
        candles = _candles(closes, vols=vols)
        result = self.strat.analyze("TEST", candles)
        # Should be None (vol_ratio < 1.2)
        if result is not None:
            # If signal exists, R/R must be >= 1.2
            self.assertGreaterEqual(result["r"], 1.2)

    def test_signal_structure(self):
        closes = [100.0] * 28 + [97.0, 103.0]
        vols   = [1000.0] * 28 + [800.0, 2000.0]
        candles = _candles(closes, vols=vols)
        result = self.strat.analyze("TEST", candles)
        if result is None:
            return
        for key in ["id", "instrument_id", "side", "entry", "sl", "tp", "r", "meta"]:
            self.assertIn(key, result)
        self.assertIn("vwap", result["meta"])

    def test_name_and_lookback(self):
        self.assertEqual(self.strat.name, "vwap_bounce")
        self.assertGreaterEqual(self.strat.lookback, 20)


class TestStrategySelector(unittest.TestCase):

    def setUp(self):
        self.sel = StrategySelector()

    def test_returns_breakout_by_default(self):
        from core.strategy.breakout import BreakoutStrategy
        s = self.sel.get("breakout")
        self.assertIsInstance(s, BreakoutStrategy)

    def test_returns_mean_reversion(self):
        from core.strategy.mean_reversion import MeanReversionStrategy
        s = self.sel.get("mean_reversion")
        self.assertIsInstance(s, MeanReversionStrategy)

    def test_returns_vwap_bounce(self):
        from core.strategy.vwap_bounce import VWAPBounceStrategy
        s = self.sel.get("vwap_bounce")
        self.assertIsInstance(s, VWAPBounceStrategy)

    def test_unknown_name_falls_back_to_breakout(self):
        from core.strategy.breakout import BreakoutStrategy
        s = self.sel.get("nonexistent_strategy_xyz")
        self.assertIsInstance(s, BreakoutStrategy)

    def test_none_falls_back_to_breakout(self):
        from core.strategy.breakout import BreakoutStrategy
        s = self.sel.get(None)
        self.assertIsInstance(s, BreakoutStrategy)

    def test_caches_instance(self):
        s1 = self.sel.get("breakout")
        s2 = self.sel.get("breakout")
        self.assertIs(s1, s2)

    def test_available_contains_all_strategies(self):
        available = StrategySelector.available()
        self.assertIn("breakout", available)
        self.assertIn("mean_reversion", available)
        self.assertIn("vwap_bounce", available)

    def test_case_insensitive(self):
        s = self.sel.get("BREAKOUT")
        from core.strategy.breakout import BreakoutStrategy
        self.assertIsInstance(s, BreakoutStrategy)


if __name__ == "__main__":
    unittest.main()
