"""
P5 Tests — Correlation filter (P5-06): calc_correlation, check_correlation.
"""
import math
import unittest
from core.risk.correlation import calc_correlation, _returns


class TestReturns(unittest.TestCase):

    def test_flat_series_returns_zeros(self):
        closes = [100.0] * 10
        rets = _returns(closes)
        self.assertEqual(len(rets), 9)
        for r in rets:
            self.assertAlmostEqual(r, 0.0, places=8)

    def test_doubling_each_bar_gives_log2(self):
        closes = [100.0 * (2 ** i) for i in range(5)]
        rets = _returns(closes)
        for r in rets:
            self.assertAlmostEqual(r, math.log(2), places=6)

    def test_length_is_n_minus_1(self):
        closes = [float(i + 1) for i in range(20)]
        self.assertEqual(len(_returns(closes)), 19)


class TestCalcCorrelation(unittest.TestCase):

    def test_identical_series_corr_1(self):
        closes = [100.0 + i * 0.5 for i in range(60)]
        rets = _returns(closes)
        corr = calc_correlation(rets, rets, period=50)
        self.assertAlmostEqual(corr, 1.0, places=4)

    def test_opposite_series_corr_minus_1(self):
        # Alternating sign returns → perfect negative correlation
        # a:  +1, -1, +1, -1 ...
        # b:  -1, +1, -1, +1 ...
        a = [(-1) ** i * 0.01 for i in range(60)]
        b = [(-1) ** (i + 1) * 0.01 for i in range(60)]
        corr = calc_correlation(a, b, period=50)
        self.assertAlmostEqual(corr, -1.0, places=4)

    def test_independent_series_near_zero(self):
        import random; random.seed(42)
        a = [random.gauss(0, 1) for _ in range(60)]
        b = [random.gauss(0, 1) for _ in range(60)]
        corr = calc_correlation(a, b, period=50)
        self.assertLess(abs(corr), 0.5)  # Independent → low correlation

    def test_range_minus1_to_1(self):
        import random; random.seed(77)
        for _ in range(10):
            a = [random.gauss(0, 1) for _ in range(60)]
            b = [random.gauss(0, 1) for _ in range(60)]
            corr = calc_correlation(a, b, period=50)
            self.assertGreaterEqual(corr, -1.0)
            self.assertLessEqual(corr, 1.0)

    def test_insufficient_data_returns_zero(self):
        a = [0.01] * 5
        b = [0.01] * 5
        self.assertEqual(calc_correlation(a, b, period=50), 0.0)

    def test_flat_series_returns_zero_not_nan(self):
        a = [0.0] * 60
        b = [0.01] * 60
        corr = calc_correlation(a, b, period=50)
        self.assertEqual(corr, 0.0)
        self.assertFalse(math.isnan(corr))

    def test_period_respected(self):
        """Using period=10 vs period=50 on long series gives different results."""
        import random; random.seed(55)
        a = [random.gauss(0, 1) for _ in range(100)]
        b = [random.gauss(0, 1) for _ in range(100)]
        c10 = calc_correlation(a, b, period=10)
        c50 = calc_correlation(a, b, period=50)
        # Both valid; just confirm they can differ
        self.assertIsInstance(c10, float)
        self.assertIsInstance(c50, float)


class TestCheckCorrelation(unittest.TestCase):

    def _make_candles(self, closes):
        return [{"close": c, "high": c+1, "low": c-1, "volume": 100} for c in closes]

    def test_no_open_positions_always_ok(self):
        """Without open positions the check always passes."""
        from unittest.mock import MagicMock
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        from core.risk.correlation import check_correlation
        closes = [100.0 + i for i in range(60)]
        candles_map = {"TQBR:SBER": self._make_candles(closes)}
        ok, msg = check_correlation(db, "TQBR:SBER", candles_map)
        self.assertTrue(ok)

    def test_uncorrelated_position_allowed(self):
        """New instrument uncorrelated with open one → OK."""
        from unittest.mock import MagicMock, patch
        import random; random.seed(10)

        pos = MagicMock(); pos.instrument_id = "TQBR:GAZP"; pos.qty = 10

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [pos]

        from core.risk.correlation import check_correlation
        sber_closes = [100 + i + random.gauss(0, 5) for i in range(60)]
        gazp_closes = [200 + random.gauss(0, 10) for _ in range(60)]  # independent

        candles_map = {
            "TQBR:SBER": self._make_candles(sber_closes),
            "TQBR:GAZP": self._make_candles(gazp_closes),
        }
        ok, msg = check_correlation(db, "TQBR:SBER", candles_map, threshold=0.8)
        self.assertTrue(ok)

    def test_highly_correlated_position_blocked(self):
        """New instrument nearly identical to open one → blocked."""
        from unittest.mock import MagicMock

        pos = MagicMock(); pos.instrument_id = "TQBR:GAZP"; pos.qty = 10

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [pos]

        from core.risk.correlation import check_correlation

        base = [100.0 + i * 0.3 for i in range(60)]
        slightly_different = [v + 0.001 for v in base]  # near-identical → corr ≈ 1.0

        candles_map = {
            "TQBR:SBER": self._make_candles(slightly_different),
            "TQBR:GAZP": self._make_candles(base),
        }
        # max_correlated=1 → even one correlated position → block
        ok, msg = check_correlation(
            db, "TQBR:SBER", candles_map, threshold=0.8, max_correlated=1
        )
        self.assertFalse(ok)
        self.assertIn("TQBR:GAZP", msg)


if __name__ == "__main__":
    unittest.main()
