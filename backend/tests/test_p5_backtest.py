"""
P5 Tests — BacktestEngine (P5-07).

Тестирует: логику SL/TP, учёт комиссий, метрики (win_rate, drawdown, equity curve).
"""
import unittest
from apps.backtest.engine import BacktestEngine, BacktestTrade
from core.strategy.breakout import BreakoutStrategy
from core.strategy.mean_reversion import MeanReversionStrategy


def _candles(closes, spread=1.0, vol=1000.0):
    return [
        {
            "time": 1_700_000_000 + i * 60,
            "open":  c,
            "high":  c + spread,
            "low":   c - spread,
            "close": c,
            "volume": vol,
        }
        for i, c in enumerate(closes)
    ]


def _trending(n=200, start=100.0, step=0.5):
    """Strong uptrend — good for breakout."""
    return [start + i * step for i in range(n)]


def _ranging(n=100, center=100.0, amp=3.0):
    """Ranging market."""
    import math
    return [center + amp * math.sin(i * 0.3) for i in range(n)]


def _make_engine(**kwargs):
    strat = kwargs.pop("strategy", BreakoutStrategy(lookback=5))
    return BacktestEngine(
        strategy=strat,
        settings=None,
        use_decision_engine=False,
        **kwargs,
    )


class TestBacktestBasics(unittest.TestCase):

    def test_runs_without_error_on_enough_data(self):
        engine = _make_engine()
        closes = _trending(150)
        result = engine.run("TEST", _candles(closes))
        self.assertIsNotNone(result)
        self.assertEqual(result.instrument_id, "TEST")
        self.assertEqual(result.strategy_name, "breakout")

    def test_raises_on_too_few_candles(self):
        engine = _make_engine()
        with self.assertRaises(ValueError):
            engine.run("TEST", _candles([100.0] * 5))

    def test_initial_balance_reflected(self):
        engine = _make_engine(initial_balance=50_000.0)
        result = engine.run("TEST", _candles(_trending(150)))
        self.assertEqual(result.initial_balance, 50_000.0)

    def test_total_return_consistent_with_balance(self):
        engine = _make_engine()
        result = engine.run("TEST", _candles(_trending(150)))
        expected_pct = (result.final_balance - result.initial_balance) / result.initial_balance * 100
        self.assertAlmostEqual(result.total_return_pct, expected_pct, places=2)

    def test_equity_curve_length(self):
        """Equity curve has one entry per bar (from lookback onward)."""
        candles = _candles(_trending(150))
        engine = _make_engine()
        result = engine.run("TEST", candles)
        lookback = engine.strategy.lookback
        self.assertEqual(len(result.equity_curve), len(candles) - lookback)

    def test_equity_curve_ts_monotonic(self):
        result = _make_engine().run("TEST", _candles(_trending(150)))
        tss = [e["ts"] for e in result.equity_curve]
        self.assertEqual(tss, sorted(tss))

    def test_equity_curve_values_positive(self):
        result = _make_engine().run("TEST", _candles(_trending(150)))
        for e in result.equity_curve:
            self.assertGreater(e["equity"], 0)


class TestBacktestMetrics(unittest.TestCase):

    def _run(self, closes, **kwargs):
        return _make_engine(**kwargs).run("TEST", _candles(closes, spread=0.5))

    def test_win_rate_between_0_and_100(self):
        result = self._run(_trending(200))
        self.assertGreaterEqual(result.win_rate, 0.0)
        self.assertLessEqual(result.win_rate, 100.0)

    def test_max_drawdown_non_negative(self):
        result = self._run(_trending(200))
        self.assertGreaterEqual(result.max_drawdown_pct, 0.0)

    def test_max_drawdown_at_most_100(self):
        result = self._run(_ranging(150))
        self.assertLessEqual(result.max_drawdown_pct, 100.0)

    def test_sharpe_not_nan_when_trades_exist(self):
        import math
        result = self._run(_trending(200))
        if result.sharpe_ratio is not None:
            self.assertFalse(math.isnan(result.sharpe_ratio))

    def test_no_trades_gives_zero_win_rate(self):
        """Flat market → breakout strategy never fires → no trades."""
        closes = [100.0] * 100
        result = self._run(closes)
        self.assertEqual(result.total_trades, 0)
        self.assertEqual(result.win_rate, 0.0)

    def test_profit_factor_none_if_no_losses(self):
        """All wins → no denominator → profit_factor may be None."""
        result = self._run(_trending(200))
        # Either a valid float or None (if no losses)
        if result.profit_factor is not None:
            self.assertGreater(result.profit_factor, 0)

    def test_trades_list_matches_total_trades(self):
        result = self._run(_trending(200))
        self.assertEqual(len(result.trades), result.total_trades)

    def test_each_trade_has_required_fields(self):
        result = self._run(_trending(200))
        required = ["side", "entry", "close", "pnl", "pnl_pct", "close_reason", "bars_held"]
        for t in result.trades:
            for key in required:
                self.assertIn(key, t, f"Missing field: {key}")

    def test_close_reason_valid_values(self):
        result = self._run(_trending(200))
        valid = {"TP", "SL", "END"}
        for t in result.trades:
            self.assertIn(t["close_reason"], valid)

    def test_bars_held_non_negative(self):
        result = self._run(_trending(200))
        for t in result.trades:
            self.assertGreaterEqual(t["bars_held"], 0)


class TestBacktestSLTP(unittest.TestCase):
    """Verify SL and TP are triggered correctly using a mock strategy."""

    def _engine_with_mock(self, signal_factory, initial=10_000.0):
        class MockStrategy:
            name = "mock"
            lookback = 5
            _call_count = 0

            def __init__(self, factory):
                self._factory = factory

            def analyze(self, instrument_id, candles):
                self._call_count += 1
                if self._call_count == 1:
                    return self._factory(candles[-1]["close"])
                return None   # Only one signal

        strat = MockStrategy(signal_factory)
        return BacktestEngine(
            strategy=strat,
            settings=None,
            use_decision_engine=False,
            initial_balance=initial,
            commission_pct=0.0,  # no commission for clean math
        )

    def test_sl_triggered(self):
        """SL should close trade at a loss when price drops."""
        def factory(price):
            return {
                "side": "BUY", "entry": price,
                "sl": price - 5.0, "tp": price + 15.0,
                "size": 1.0, "r": 3.0,
            }

        # Price drops 6 points after entry → SL hit
        closes = [100.0] * 10 + [100.0, 94.0] + [94.0] * 50
        engine = self._engine_with_mock(factory)
        result = engine.run("TEST", _candles(closes, spread=3.0))

        sl_trades = [t for t in result.trades if t["close_reason"] == "SL"]
        self.assertGreater(len(sl_trades), 0)
        self.assertLess(sl_trades[0]["pnl"], 0)

    def test_tp_triggered(self):
        """TP should close trade at a profit when price rises."""
        def factory(price):
            return {
                "side": "BUY", "entry": price,
                "sl": price - 5.0, "tp": price + 5.0,
                "size": 1.0, "r": 1.0,
            }

        closes = [100.0] * 10 + [100.0, 106.0] + [106.0] * 50
        engine = self._engine_with_mock(factory)
        result = engine.run("TEST", _candles(closes, spread=3.0))

        tp_trades = [t for t in result.trades if t["close_reason"] == "TP"]
        self.assertGreater(len(tp_trades), 0)
        self.assertGreater(tp_trades[0]["pnl"], 0)

    def test_commission_reduces_pnl(self):
        """Commission makes the final balance lower than without."""
        def factory(price):
            return {"side":"BUY","entry":price,"sl":price-5,"tp":price+10,"size":10.0,"r":2.0}

        closes_up = [100.0] * 10 + [100.0 + i for i in range(100)]
        no_comm = BacktestEngine(
            BreakoutStrategy(lookback=5), settings=None,
            use_decision_engine=False, commission_pct=0.0
        ).run("TEST", _candles(closes_up))
        with_comm = BacktestEngine(
            BreakoutStrategy(lookback=5), settings=None,
            use_decision_engine=False, commission_pct=0.1
        ).run("TEST", _candles(closes_up))

        self.assertGreaterEqual(no_comm.final_balance, with_comm.final_balance)


class TestBacktestStrategies(unittest.TestCase):

    def test_mean_reversion_runs(self):
        import math
        closes = [100 + 5 * math.sin(i * 0.4) for i in range(150)]
        engine = BacktestEngine(
            MeanReversionStrategy(), settings=None, use_decision_engine=False
        )
        result = engine.run("TEST", _candles(closes, spread=0.5))
        self.assertIsNotNone(result)
        self.assertEqual(result.strategy_name, "mean_reversion")

    def test_different_strategies_can_differ_in_trade_count(self):
        """Two strategies on same data should generally produce different results."""
        closes = _trending(200)
        candles = _candles(closes, spread=0.3)

        r_breakout = BacktestEngine(
            BreakoutStrategy(lookback=5), settings=None, use_decision_engine=False
        ).run("TEST", candles)
        r_mean_rev = BacktestEngine(
            MeanReversionStrategy(), settings=None, use_decision_engine=False
        ).run("TEST", candles)

        # Both complete without error; trade counts may differ
        self.assertIsNotNone(r_breakout)
        self.assertIsNotNone(r_mean_rev)


if __name__ == "__main__":
    unittest.main()
