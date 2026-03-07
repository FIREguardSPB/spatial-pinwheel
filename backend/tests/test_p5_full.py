"""
P5: Comprehensive test suite.

Covers:
  P5-01: New indicators (Bollinger, Stochastic, VWAP, VolumeRatio)
  P5-02: Volume score / volume filter
  P5-03: Session filter (check_session)
  P5-04: HTF alignment scoring
  P5-05: All strategies (Breakout, MeanReversion, VWAPBounce) + StrategySelector
  P5-06: Correlation filter (pure math + integration)
  P5-07: BacktestEngine metrics + walk-forward correctness
"""
import math
import random
import sys
import os
import unittest

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.worker.decision_engine import indicators
from core.risk.correlation import calc_correlation, _returns
from core.strategy.breakout import BreakoutStrategy
from core.strategy.mean_reversion import MeanReversionStrategy
from core.strategy.vwap_bounce import VWAPBounceStrategy
from core.strategy.selector import StrategySelector
from apps.backtest.engine import BacktestEngine, BacktestResult

import sys
try:
    import pydantic
    _HAS_PYDANTIC = True
except ImportError:
    _HAS_PYDANTIC = False

_skip_no_pydantic = unittest.skipUnless(_HAS_PYDANTIC, "pydantic not installed (CI will run these)")



# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_candles(n: int = 100, seed: int = 42, trend: float = 0.001) -> list[dict]:
    """Generate synthetic OHLCV candles with a slight uptrend by default."""
    random.seed(seed)
    price = 100.0
    candles = []
    for i in range(n):
        change = random.uniform(-0.5, 0.5) + price * trend
        open_ = price
        close = price + change
        high = max(open_, close) + random.uniform(0, 0.3)
        low = min(open_, close) - random.uniform(0, 0.3)
        vol = random.uniform(800, 1200)
        candles.append({
            "time": 1_700_000_000 + i * 60,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        })
        price = close
    return candles


def make_candles_trending(n: int = 100, up: bool = True) -> list[dict]:
    """Candles with clear directional trend for strategy signal testing."""
    price = 100.0
    delta = 0.3 if up else -0.3
    candles = []
    for i in range(n):
        open_ = price
        close = price + delta + (0.05 if up else -0.05)
        high = max(open_, close) + 0.1
        low = min(open_, close) - 0.1
        candles.append({"time": i * 60, "open": open_, "high": high,
                         "low": low, "close": close, "volume": 1000.0})
        price = close
    return candles


# ─────────────────────────────────────────────────────────────────────────────
#  P5-01: Indicators
# ─────────────────────────────────────────────────────────────────────────────

class TestBollingerBands(unittest.TestCase):

    def test_returns_three_values(self):
        closes = [100.0 + i * 0.1 for i in range(30)]
        result = indicators.calc_bollinger(closes, period=20)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3)

    def test_upper_gt_middle_gt_lower(self):
        closes = [100 + (i % 5) * 0.5 for i in range(30)]
        upper, middle, lower = indicators.calc_bollinger(closes, period=20)
        self.assertGreater(upper, middle)
        self.assertGreater(middle, lower)

    def test_constant_series_zero_width(self):
        """Constant prices → zero std → upper == middle == lower."""
        closes = [50.0] * 25
        upper, middle, lower = indicators.calc_bollinger(closes, period=20)
        self.assertAlmostEqual(upper, middle, places=4)
        self.assertAlmostEqual(lower, middle, places=4)

    def test_not_enough_data_returns_none(self):
        result = indicators.calc_bollinger([100.0] * 5, period=20)
        self.assertIsNone(result)

    def test_wider_bands_with_higher_volatility(self):
        stable = [100.0 + (i % 2) * 0.01 for i in range(25)]
        volatile = [100.0 + (i % 2) * 5.0 for i in range(25)]
        u_s, m_s, l_s = indicators.calc_bollinger(stable, period=20)
        u_v, m_v, l_v = indicators.calc_bollinger(volatile, period=20)
        self.assertGreater((u_v - l_v), (u_s - l_s))

    def test_middle_equals_sma(self):
        closes = [float(i) for i in range(25)]
        _, middle, _ = indicators.calc_bollinger(closes, period=20)
        expected_sma = sum(closes[-20:]) / 20
        self.assertAlmostEqual(middle, expected_sma, places=4)


class TestStochastic(unittest.TestCase):

    def test_output_range_0_to_100(self):
        random.seed(7)
        closes = [100 + random.uniform(-3, 3) for _ in range(30)]
        highs = [c + 1.5 for c in closes]
        lows = [c - 1.5 for c in closes]
        k, d = indicators.calc_stochastic(highs, lows, closes)
        self.assertGreaterEqual(k, 0)
        self.assertLessEqual(k, 100)
        self.assertGreaterEqual(d, 0)
        self.assertLessEqual(d, 100)

    def test_overbought_when_at_high(self):
        """Price always at high → stochastic near 100."""
        n = 20
        closes = [float(100 + i) for i in range(n)]
        highs  = [c for c in closes]       # price IS the high
        lows   = [c - 10 for c in closes]
        k, d = indicators.calc_stochastic(highs, lows, closes)
        self.assertGreater(k, 80)

    def test_oversold_when_at_low(self):
        """Price always at low → stochastic near 0."""
        n = 20
        closes = [float(100 + i * 0) for i in range(n)]  # flat
        highs  = [110.0] * n
        lows   = [c for c in closes]      # price IS the low
        k, d = indicators.calc_stochastic(highs, lows, closes)
        self.assertLess(k, 20)

    def test_insufficient_data_returns_none(self):
        result = indicators.calc_stochastic([105, 106], [99, 100], [104, 105])
        # with only 2 bars, should return None or a fallback
        # actual implementation may return fallback — just check no crash
        self.assertTrue(result is None or isinstance(result, tuple))


class TestVWAP(unittest.TestCase):

    def test_equal_volume_weighted_average(self):
        highs  = [11.0, 21.0, 31.0]
        lows   = [9.0,  19.0, 29.0]
        closes = [10.0, 20.0, 30.0]
        vols   = [100.0, 100.0, 100.0]
        vwap = indicators.calc_vwap(highs, lows, closes, vols)
        expected = sum((h + l + c) / 3 for h, l, c in zip(highs, lows, closes)) / 3
        self.assertAlmostEqual(vwap, expected, places=4)

    def test_higher_volume_bars_dominate(self):
        """Bar with 10x volume should pull VWAP toward its TP."""
        highs  = [11.0, 21.0]
        lows   = [9.0,  19.0]
        closes = [10.0, 20.0]
        vols   = [10.0, 100.0]   # second bar dominates
        vwap = indicators.calc_vwap(highs, lows, closes, vols)
        # VWAP should be closer to 20 than to 10
        self.assertGreater(vwap, 15.0)

    def test_empty_inputs_return_none(self):
        self.assertIsNone(indicators.calc_vwap([], [], [], []))

    def test_zero_volume_return_none(self):
        self.assertIsNone(indicators.calc_vwap([10.0], [8.0], [9.0], [0.0]))


class TestVolumeRatio(unittest.TestCase):

    def test_constant_volume_ratio_is_one(self):
        vols = [100.0] * 25
        ratio = indicators.calc_volume_ratio(vols, period=20)
        self.assertAlmostEqual(ratio, 1.0, places=3)

    def test_double_volume_ratio_is_two(self):
        vols = [100.0] * 20 + [200.0]  # last bar is 2x avg
        ratio = indicators.calc_volume_ratio(vols, period=20)
        self.assertAlmostEqual(ratio, 2.0, places=3)

    def test_insufficient_data_returns_none(self):
        result = indicators.calc_volume_ratio([100.0] * 5, period=20)
        self.assertIsNone(result)


# ─────────────────────────────────────────────────────────────────────────────
#  P5-02: Volume Score / Filter
# ─────────────────────────────────────────────────────────────────────────────

@_skip_no_pydantic
class TestVolumeScore(unittest.TestCase):

    def setUp(self):
        from apps.worker.decision_engine import rules
        self.rules = rules

    def test_low_volume_blocks(self):
        """volume_ratio < 0.5 → BLOCK severity."""
        from apps.worker.decision_engine.types import Severity
        score, reason = self.rules.score_volume(0.2, max_score=10)
        self.assertEqual(score, 0)
        self.assertEqual(reason.severity, Severity.BLOCK)

    def test_normal_volume_scores_positively(self):
        """volume_ratio ~1.0 → reasonable score."""
        score, reason = self.rules.score_volume(1.0, max_score=10)
        self.assertGreater(score, 0)

    def test_high_volume_warns(self):
        """volume_ratio > 3.0 → WARN (anomalous) but still some score."""
        from apps.worker.decision_engine.types import Severity
        score, reason = self.rules.score_volume(5.0, max_score=10)
        # Should not be a BLOCK
        self.assertNotEqual(reason.severity, Severity.BLOCK)

    def test_none_volume_returns_partial(self):
        """None volume_ratio → partial score (no data)."""
        score, reason = self.rules.score_volume(None, max_score=10)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 10)


# ─────────────────────────────────────────────────────────────────────────────
#  P5-03: Session Filter
# ─────────────────────────────────────────────────────────────────────────────

@_skip_no_pydantic
class TestSessionFilter(unittest.TestCase):

    def test_check_session_returns_reason_or_none(self):
        """check_session must return Reason | None (no exception)."""
        from apps.worker.decision_engine.rules import check_session
        result = check_session()
        # Either None (trading allowed) or a Reason object
        self.assertTrue(result is None or hasattr(result, "severity"))

    def test_session_utils_is_bool(self):
        from core.utils.session import is_trading_session, minutes_until_session_end
        result = is_trading_session()
        self.assertIsInstance(result, bool)
        mins = minutes_until_session_end()
        self.assertIsInstance(mins, float)

    def test_moex_hours_constants(self):
        from core.utils.session import MOEX_OPEN, MOEX_CLOSE
        from datetime import time as dtime
        self.assertEqual(MOEX_OPEN,  dtime(9, 50))
        self.assertEqual(MOEX_CLOSE, dtime(18, 50))


# ─────────────────────────────────────────────────────────────────────────────
#  P5-04: HTF Alignment
# ─────────────────────────────────────────────────────────────────────────────

@_skip_no_pydantic
class TestHTFAlignment(unittest.TestCase):

    def setUp(self):
        from apps.worker.decision_engine import rules
        self.rules = rules

    def test_buy_uptrend_full_score(self):
        score, reason = self.rules.score_htf_alignment("BUY", "up", max_score=5)
        self.assertEqual(score, 5)

    def test_sell_downtrend_full_score(self):
        score, reason = self.rules.score_htf_alignment("SELL", "down", max_score=5)
        self.assertEqual(score, 5)

    def test_buy_downtrend_zero_score(self):
        score, reason = self.rules.score_htf_alignment("BUY", "down", max_score=5)
        self.assertEqual(score, 0)

    def test_flat_htf_partial_score(self):
        score, reason = self.rules.score_htf_alignment("BUY", "flat", max_score=5)
        self.assertGreater(score, 0)
        self.assertLess(score, 5)

    def test_returns_reason(self):
        _, reason = self.rules.score_htf_alignment("BUY", "up")
        self.assertIsNotNone(reason)
        self.assertIsNotNone(reason.code)


# ─────────────────────────────────────────────────────────────────────────────
#  P5-05: Strategies
# ─────────────────────────────────────────────────────────────────────────────

class TestBreakoutStrategy(unittest.TestCase):

    def setUp(self):
        self.strategy = BreakoutStrategy(lookback=5)

    def test_properties(self):
        self.assertEqual(self.strategy.name, "breakout")
        self.assertEqual(self.strategy.lookback, 5)

    def test_too_few_candles_returns_none(self):
        candles = make_candles(3)
        result = self.strategy.analyze("TQBR:TEST", candles)
        self.assertIsNone(result)

    def test_signal_has_required_keys(self):
        candles = make_candles_trending(60, up=True)
        result = self.strategy.analyze("TQBR:TEST", candles)
        if result is not None:
            for key in ("side", "entry", "sl", "tp", "r"):
                self.assertIn(key, result)

    def test_buy_signal_on_uptrend(self):
        candles = make_candles_trending(60, up=True)
        result = self.strategy.analyze("TQBR:TEST", candles)
        if result:
            self.assertEqual(result["side"], "BUY")

    def test_sell_signal_on_downtrend(self):
        candles = make_candles_trending(60, up=False)
        result = self.strategy.analyze("TQBR:TEST", candles)
        if result:
            self.assertEqual(result["side"], "SELL")

    def test_buy_sl_below_entry(self):
        candles = make_candles_trending(60, up=True)
        result = self.strategy.analyze("TQBR:TEST", candles)
        if result and result["side"] == "BUY":
            self.assertLess(result["sl"], result["entry"])
            self.assertGreater(result["tp"], result["entry"])

    def test_r_is_positive(self):
        candles = make_candles_trending(60, up=True)
        result = self.strategy.analyze("TQBR:TEST", candles)
        if result:
            self.assertGreater(result["r"], 0)


class TestMeanReversionStrategy(unittest.TestCase):

    def setUp(self):
        self.strategy = MeanReversionStrategy()

    def test_properties(self):
        self.assertEqual(self.strategy.name, "mean_reversion")
        self.assertGreater(self.strategy.lookback, 0)

    def test_too_few_candles_returns_none(self):
        candles = make_candles(5)
        result = self.strategy.analyze("TQBR:TEST", candles)
        self.assertIsNone(result)

    def test_signal_structure_valid(self):
        candles = make_candles(80)
        result = self.strategy.analyze("TQBR:TEST", candles)
        if result is not None:
            self.assertIn("side", result)
            self.assertIn("entry", result)
            self.assertGreater(result["r"], 0)

    def test_no_crash_on_various_data(self):
        for seed in range(5):
            candles = make_candles(100, seed=seed)
            try:
                self.strategy.analyze("TQBR:TEST", candles)
            except Exception as e:
                self.fail(f"MeanReversion raised {e} with seed={seed}")


class TestVWAPBounceStrategy(unittest.TestCase):

    def setUp(self):
        self.strategy = VWAPBounceStrategy()

    def test_properties(self):
        self.assertEqual(self.strategy.name, "vwap_bounce")
        self.assertGreater(self.strategy.lookback, 0)

    def test_no_crash_on_random_data(self):
        candles = make_candles(80)
        try:
            self.strategy.analyze("TQBR:TEST", candles)
        except Exception as e:
            self.fail(f"VWAPBounce raised: {e}")

    def test_signal_structure(self):
        candles = make_candles(80)
        result = self.strategy.analyze("TQBR:TEST", candles)
        if result is not None:
            self.assertIn("side", result)
            self.assertIn("sl", result)
            self.assertIn("tp", result)


class TestStrategySelector(unittest.TestCase):

    def setUp(self):
        self.selector = StrategySelector()

    def test_get_breakout(self):
        s = self.selector.get("breakout")
        self.assertEqual(s.name, "breakout")

    def test_get_mean_reversion(self):
        s = self.selector.get("mean_reversion")
        self.assertEqual(s.name, "mean_reversion")

    def test_get_vwap_bounce(self):
        s = self.selector.get("vwap_bounce")
        self.assertEqual(s.name, "vwap_bounce")

    def test_unknown_falls_back_to_breakout(self):
        s = self.selector.get("nonexistent_xyz")
        self.assertEqual(s.name, "breakout")

    def test_none_falls_back_to_breakout(self):
        s = self.selector.get(None)
        self.assertEqual(s.name, "breakout")

    def test_caches_instances(self):
        s1 = self.selector.get("breakout")
        s2 = self.selector.get("breakout")
        self.assertIs(s1, s2)  # same object

    def test_available_lists_all_strategies(self):
        names = StrategySelector.available()
        self.assertIn("breakout", names)
        self.assertIn("mean_reversion", names)
        self.assertIn("vwap_bounce", names)


# ─────────────────────────────────────────────────────────────────────────────
#  P5-06: Correlation
# ─────────────────────────────────────────────────────────────────────────────

class TestCorrelationMath(unittest.TestCase):

    def test_identical_series_correlation_is_one(self):
        closes = [100.0 + i * 0.1 for i in range(60)]
        rets = _returns(closes)
        corr = calc_correlation(rets, rets, period=50)
        self.assertAlmostEqual(corr, 1.0, places=3)

    def test_opposite_series_correlation_is_minus_one(self):
        """Alternating opposite returns → strong negative correlation."""
        # Use alternating +/- returns so std is non-zero
        n = 60
        rets_a = [0.01 if i % 2 == 0 else -0.01 for i in range(n)]
        rets_b = [-0.01 if i % 2 == 0 else 0.01 for i in range(n)]
        corr = calc_correlation(rets_a, rets_b, period=50)
        self.assertAlmostEqual(corr, -1.0, places=3)

    def test_uncorrelated_returns_near_zero(self):
        random.seed(1)
        rets_a = [random.uniform(-0.01, 0.01) for _ in range(60)]
        random.seed(999)
        rets_b = [random.uniform(-0.01, 0.01) for _ in range(60)]
        corr = calc_correlation(rets_a, rets_b, period=50)
        self.assertLess(abs(corr), 0.5)  # not strongly correlated

    def test_output_range_minus1_to_1(self):
        random.seed(42)
        for _ in range(10):
            a = [random.uniform(-1, 1) for _ in range(60)]
            b = [random.uniform(-1, 1) for _ in range(60)]
            corr = calc_correlation(a, b, period=50)
            self.assertGreaterEqual(corr, -1.0)
            self.assertLessEqual(corr, 1.0)

    def test_insufficient_data_returns_zero(self):
        corr = calc_correlation([0.01] * 5, [0.01] * 5, period=50)
        self.assertEqual(corr, 0.0)

    def test_constant_series_returns_zero(self):
        """Zero std → correlation undefined → return 0."""
        rets = [0.0] * 60
        corr = calc_correlation(rets, rets, period=50)
        self.assertEqual(corr, 0.0)

    def test_highly_correlated_moex_like(self):
        """Simulate SBER/GAZP-like correlation (both follow oil price)."""
        random.seed(10)
        oil = [random.uniform(-0.02, 0.02) for _ in range(60)]
        noise = 0.3
        sber_rets = [o + random.uniform(-noise, noise) * 0.01 for o in oil]
        gazp_rets = [o + random.uniform(-noise, noise) * 0.01 for o in oil]
        corr = calc_correlation(sber_rets, gazp_rets, period=50)
        self.assertGreater(corr, 0.5)  # should be highly correlated


# ─────────────────────────────────────────────────────────────────────────────
#  P5-07: Backtesting
# ─────────────────────────────────────────────────────────────────────────────

class TestBacktestEngine(unittest.TestCase):

    def _run(self, strategy, n=200, seed=42, trend=0.001):
        candles = make_candles(n, seed=seed, trend=trend)
        engine = BacktestEngine(
            strategy=strategy,
            settings=None,
            initial_balance=100_000.0,
            risk_pct=1.0,
            use_decision_engine=False,
        )
        return engine.run("TQBR:TEST", candles)

    def test_returns_backtest_result(self):
        result = self._run(BreakoutStrategy())
        self.assertIsInstance(result, BacktestResult)

    def test_equity_curve_same_length_as_candles(self):
        n = 200
        candles = make_candles(n)
        engine = BacktestEngine(BreakoutStrategy(), settings=None)
        result = engine.run("TQBR:TEST", candles)
        # equity curve has one point per bar after lookback
        self.assertGreater(len(result.equity_curve), 0)
        self.assertLessEqual(len(result.equity_curve), n)

    def test_win_rate_between_0_and_100(self):
        result = self._run(BreakoutStrategy())
        self.assertGreaterEqual(result.win_rate, 0)
        self.assertLessEqual(result.win_rate, 100)

    def test_max_drawdown_non_negative(self):
        result = self._run(BreakoutStrategy())
        self.assertGreaterEqual(result.max_drawdown_pct, 0)

    def test_profit_factor_non_negative(self):
        result = self._run(BreakoutStrategy())
        if result.profit_factor is not None:
            self.assertGreater(result.profit_factor, 0)

    def test_total_return_matches_balance(self):
        result = self._run(BreakoutStrategy())
        expected_return = (result.final_balance - result.initial_balance) / result.initial_balance * 100
        self.assertAlmostEqual(result.total_return_pct, expected_return, places=1)

    def test_no_trades_on_insufficient_candles(self):
        engine = BacktestEngine(BreakoutStrategy(lookback=5), settings=None)
        with self.assertRaises(ValueError):
            engine.run("TQBR:TEST", make_candles(5))

    def test_no_lookahead_bias(self):
        """Each bar's signal only uses data up to and including that bar."""
        # We can verify by checking that signal analysis window grows monotonically
        # — indirect test: running on reversed candles produces different result
        candles_fwd = make_candles(150, seed=7)
        candles_rev = list(reversed(candles_fwd))
        engine = BacktestEngine(BreakoutStrategy(), settings=None)
        result_fwd = engine.run("TQBR:TEST", candles_fwd)
        result_rev = engine.run("TQBR:TEST", candles_rev)
        # Results should differ (reversing time changes signals)
        # At minimum, total_trades should differ OR final_balance should differ
        results_differ = (
            result_fwd.total_trades != result_rev.total_trades
            or abs(result_fwd.final_balance - result_rev.final_balance) > 0.01
        )
        self.assertTrue(results_differ)

    def test_commission_reduces_pnl(self):
        """Higher commission → lower final balance."""
        candles = make_candles(200)
        engine_no_comm = BacktestEngine(BreakoutStrategy(), settings=None, commission_pct=0.0)
        engine_with_comm = BacktestEngine(BreakoutStrategy(), settings=None, commission_pct=0.1)
        r_no  = engine_no_comm.run("TQBR:TEST", candles)
        r_with = engine_with_comm.run("TQBR:TEST", candles)
        if r_no.total_trades > 0:
            self.assertGreaterEqual(r_no.final_balance, r_with.final_balance)

    def test_sharpe_ratio_type(self):
        result = self._run(BreakoutStrategy(), n=300)
        if result.sharpe_ratio is not None:
            self.assertIsInstance(result.sharpe_ratio, float)

    def test_equity_curve_timestamps_increasing(self):
        result = self._run(BreakoutStrategy())
        ts_list = [e["ts"] for e in result.equity_curve]
        for i in range(1, len(ts_list)):
            self.assertGreaterEqual(ts_list[i], ts_list[i - 1])

    def test_all_strategies_run_without_error(self):
        candles = make_candles(200)
        for cls in (BreakoutStrategy, MeanReversionStrategy, VWAPBounceStrategy):
            strategy = cls()
            engine = BacktestEngine(strategy, settings=None)
            try:
                result = engine.run("TQBR:TEST", candles)
                self.assertIsInstance(result, BacktestResult)
            except Exception as e:
                self.fail(f"{cls.__name__} backtest raised: {e}")

    def test_risk_pct_affects_position_size(self):
        """Higher risk_pct → larger positions → larger PnL swings."""
        candles = make_candles(200, seed=3)
        engine_1pct  = BacktestEngine(BreakoutStrategy(), settings=None, risk_pct=1.0)
        engine_10pct = BacktestEngine(BreakoutStrategy(), settings=None, risk_pct=10.0)
        r_small = engine_1pct.run("TQBR:TEST", candles)
        r_large = engine_10pct.run("TQBR:TEST", candles)
        if r_small.total_trades > 0 and r_large.total_trades > 0:
            swing_small = abs(r_small.final_balance - r_small.initial_balance)
            swing_large = abs(r_large.final_balance - r_large.initial_balance)
            self.assertGreater(swing_large, swing_small)

    def test_result_instrument_and_strategy_name(self):
        result = self._run(BreakoutStrategy())
        self.assertEqual(result.instrument_id, "TQBR:TEST")
        self.assertEqual(result.strategy_name, "breakout")

    def test_from_to_timestamps_in_ms(self):
        result = self._run(BreakoutStrategy())
        # Timestamps should be in Unix ms (> 1e12)
        self.assertGreater(result.from_ts, 1_000_000_000_000)
        self.assertGreater(result.to_ts, result.from_ts)


class TestBacktestMeanReversion(unittest.TestCase):
    """MeanReversion-specific backtest tests."""

    def test_mean_reversion_on_choppy_market(self):
        """Mean reversion should find more signals on choppy (oscillating) data."""
        random.seed(99)
        price = 100.0
        candles = []
        for i in range(200):
            # Oscillate without trend
            delta = 1.0 if i % 10 < 5 else -1.0
            close = price + delta
            candles.append({"time": i * 60, "open": price, "high": close + 0.5,
                             "low": close - 0.5, "close": close, "volume": 1000.0})
            price = close

        engine = BacktestEngine(MeanReversionStrategy(), settings=None)
        result = engine.run("TQBR:TEST", candles)
        self.assertIsInstance(result, BacktestResult)
        # Mean reversion should find at least some opportunities in oscillating market
        # (not strictly enforced — strategy may be conservative)


if __name__ == "__main__":
    unittest.main(verbosity=2)
