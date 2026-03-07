"""
P7-02: Integration tests — полный цикл signal → DE → execution.

Использует in-memory SQLite (встроен в Python) вместо PostgreSQL/testcontainers,
чтобы работать без внешних зависимостей.

Run: python -m unittest tests.test_integration -v
"""
import asyncio
import os
import sys
import types
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Stub heavy deps ────────────────────────────────────────────────────────────
for _mod in ["redis", "redis.asyncio", "structlog", "grpc", "prometheus_client",
             "prometheus_client.exposition", "google", "google.protobuf",
             "tinkoff", "tinkoff.invest", "httpx"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

try:
    import pydantic as _pydantic
    _HAS_PYDANTIC = hasattr(_pydantic, 'VERSION') and hasattr(_pydantic, 'field_validator')
except ImportError:
    _HAS_PYDANTIC = False
    _pd = types.ModuleType("pydantic")
    class _BM:
        def __init__(self, **kw):
            for k, v in kw.items(): setattr(self, k, v)
        def model_dump(self): return self.__dict__
    _pd.BaseModel = _BM
    _pd.Field = lambda *a, **kw: kw.get("default", None)
    _pd.validator = lambda *a, **kw: (lambda f: f)
    _pd.field_validator = lambda *a, **kw: (lambda f: f)
    sys.modules.setdefault("pydantic", _pd)
    sys.modules.setdefault("pydantic_settings",
        types.ModuleType("pydantic_settings"))

try:
    import sqlalchemy
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    _HAS_SQLALCHEMY = True
except ImportError:
    _HAS_SQLALCHEMY = False

_skip_no_sa = unittest.skipUnless(_HAS_SQLALCHEMY, "sqlalchemy not installed")

_skip_no_pydantic = unittest.skipUnless(_HAS_PYDANTIC, "pydantic not installed")


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ══════════════════════════════════════════════════════════════════════════════
# In-process pipeline helpers (no DB required)
# ══════════════════════════════════════════════════════════════════════════════
def _make_signal(side="BUY", entry=100.0, sl=95.0, tp=110.0,
                 size=10, instrument_id="TQBR:SBER"):
    """Create a plain dict-based signal for DE evaluation."""
    return {
        "id":            "sig_test_001",
        "instrument_id": instrument_id,
        "side":          side,
        "entry":         entry,
        "sl":            sl,
        "tp":            tp,
        "size":          size,
        "r":             round(abs(tp - entry) / abs(entry - sl), 2),
        "reason":        "Integration test signal",
        "status":        "pending_review",
        "meta":          {},
    }


def _make_snapshot(closes=None, volumes=None):
    """Create a minimal MarketSnapshot-like dict."""
    if closes is None:
        closes = [100.0 + i * 0.1 for i in range(50)]
    if volumes is None:
        volumes = [10_000.0] * len(closes)
    return {
        "closes":   closes,
        "highs":    [c + 0.5  for c in closes],
        "lows":     [c - 0.5  for c in closes],
        "volumes":  volumes,
        "htf_closes": closes[-10:],
    }


def _make_settings_orm():
    """Create a MagicMock that behaves like a Settings ORM row."""
    s = MagicMock()
    s.decision_threshold          = 50
    s.rr_min                      = 1.3
    s.atr_stop_hard_min           = 0.1
    s.atr_stop_hard_max           = 10.0
    s.atr_stop_soft_min           = 0.2
    s.atr_stop_soft_max           = 5.0
    s.w_regime                    = 20
    s.w_volatility                = 15
    s.w_momentum                  = 15
    s.w_levels                    = 20
    s.w_costs                     = 15
    s.w_liquidity                 = 5
    s.w_htf                       = 10
    s.no_trade_opening_minutes    = 0
    s.close_before_session_end_minutes = 0
    s.commission_pct              = 0.05
    s.slippage_pct                = 0.05
    s.min_volume_ratio            = 0.0
    s.htf_weight                  = 10
    s.session_type                = "main"
    return s


# ══════════════════════════════════════════════════════════════════════════════
# P7-02-A  DecisionEngine pipeline (in-process, no DB)
# ══════════════════════════════════════════════════════════════════════════════
@_skip_no_pydantic
class TestDecisionEnginePipeline(unittest.TestCase):
    """Full signal → DE evaluation integration tests."""

    def _evaluate(self, signal_dict, settings=None):
        """Run DecisionEngine.evaluate on a signal dict."""
        from apps.worker.decision_engine.engine import DecisionEngine
        from apps.worker.decision_engine.types import MarketSnapshot, Decision

        if settings is None:
            settings = _make_settings_orm()

        snap_data = _make_snapshot()
        candles_list = [
            {"time": i*60, "open": h-0.5, "high": h, "low": l, "close": c, "volume": v}
            for i, (h, l, c, v) in enumerate(zip(
                snap_data["highs"], snap_data["lows"],
                snap_data["closes"], snap_data["volumes"]
            ))
        ]
        snapshot = MarketSnapshot(candles=candles_list, last_price=snap_data["closes"][-1])

        class FakeSignal:
            def __init__(self, d):
                for k, v in d.items(): setattr(self, k, v)

        sig = FakeSignal(signal_dict)
        engine = DecisionEngine(settings)

        # Patch session filter to avoid real-time dependency
        with patch("apps.worker.decision_engine.rules.check_session",
                   return_value=None):
            result = engine.evaluate(sig, snapshot)

        return result

    def test_valid_signal_produces_decision(self):
        """Valid signal → DE returns a DecisionResult."""
        from apps.worker.decision_engine.types import Decision
        sig    = _make_signal(sl=95.0, tp=115.0)  # R/R = 3.0
        result = self._evaluate(sig)
        self.assertIsNotNone(result)
        self.assertIn(result.decision, (Decision.TAKE, Decision.SKIP, Decision.REJECT))

    def test_good_rr_not_rejected(self):
        """Signal with R/R = 3.0 must not be hard-rejected (may be SKIP/TAKE)."""
        from apps.worker.decision_engine.types import Decision
        sig    = _make_signal(entry=100.0, sl=95.0, tp=115.0)
        result = self._evaluate(sig)
        self.assertNotEqual(result.decision, Decision.REJECT,
                             f"High R/R signal should not be REJECT. reasons: {result.reasons}")

    def test_bad_rr_rejected(self):
        """Signal with R/R < rr_min=1.3 must be REJECT."""
        from apps.worker.decision_engine.types import Decision
        s = _make_settings_orm()
        s.rr_min = 1.3
        # R/R = 0.5: tp only 2.5 away, sl 5 away
        sig    = _make_signal(entry=100.0, sl=95.0, tp=102.5)
        result = self._evaluate(sig, settings=s)
        self.assertEqual(result.decision, Decision.REJECT)

    def test_inverted_sl_tp_rejected(self):
        """BUY with SL > entry must be hard-rejected."""
        from apps.worker.decision_engine.types import Decision
        sig = _make_signal(side="BUY", entry=100.0, sl=105.0, tp=110.0)
        result = self._evaluate(sig)
        self.assertEqual(result.decision, Decision.REJECT)

    def test_zero_size_rejected(self):
        """Signal with size=0 must be hard-rejected."""
        from apps.worker.decision_engine.types import Decision
        sig = _make_signal(size=0)
        result = self._evaluate(sig)
        self.assertEqual(result.decision, Decision.REJECT)

    def test_score_is_0_to_100(self):
        """DE score must always be in [0, 100]."""
        sig    = _make_signal()
        result = self._evaluate(sig)
        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score,    100)

    def test_reasons_list_non_empty(self):
        """DE result always includes at least one reason."""
        sig    = _make_signal()
        result = self._evaluate(sig)
        self.assertIsInstance(result.reasons, list)
        self.assertGreater(len(result.reasons), 0)

    def test_high_threshold_forces_skip(self):
        """decision_threshold=99 → marginal signals become SKIP."""
        from apps.worker.decision_engine.types import Decision
        s = _make_settings_orm()
        s.decision_threshold = 99  # Almost impossible to meet
        sig    = _make_signal()
        result = self._evaluate(sig, settings=s)
        self.assertIn(result.decision, (Decision.SKIP, Decision.REJECT))

    def test_session_block_rejects(self):
        """When check_session returns a blocking Reason → signal REJECTED."""
        from apps.worker.decision_engine.types import Decision, Reason, ReasonCode, Severity
        from apps.worker.decision_engine.engine import DecisionEngine
        from apps.worker.decision_engine.types import MarketSnapshot

        block_reason = Reason(
            code=ReasonCode.SESSION_CLOSED,
            severity=Severity.BLOCK,
            msg="Outside MOEX trading session",
        )
        sd = _make_snapshot()
        snap_candles = [
            {"time": i*60, "open": h-0.5, "high": h, "low": l, "close": c, "volume": v}
            for i, (h, l, c, v) in enumerate(zip(sd["highs"], sd["lows"], sd["closes"], sd["volumes"]))
        ]
        snap = MarketSnapshot(candles=snap_candles, last_price=sd["closes"][-1])
        engine = DecisionEngine(_make_settings_orm())

        class FakeSig:
            side = "BUY"; entry = 100.0; sl = 95.0; tp = 110.0; size = 10
            instrument_id = "TQBR:SBER"

        with patch("apps.worker.decision_engine.rules.check_session",
                   return_value=block_reason):
            result = engine.evaluate(FakeSig(), snap)

        self.assertEqual(result.decision, Decision.REJECT)

    def test_sell_signal_evaluated(self):
        """SELL signal is accepted by DE without crashing."""
        sig = _make_signal(side="SELL", entry=100.0, sl=105.0, tp=90.0)
        result = self._evaluate(sig)
        self.assertIsNotNone(result)

    def test_deterministic_for_same_input(self):
        """Same input → same decision (DE is deterministic)."""
        sig     = _make_signal()
        result1 = self._evaluate(sig)
        result2 = self._evaluate(sig)
        self.assertEqual(result1.decision, result2.decision)
        self.assertEqual(result1.score,    result2.score)


# ══════════════════════════════════════════════════════════════════════════════
# P7-02-B  Paper execution pipeline (in-process)
# ══════════════════════════════════════════════════════════════════════════════
class TestPaperExecutionPipeline(unittest.TestCase):
    """PaperBroker signal-to-position integration."""

    def _load_paper_broker(self):
        """Load PaperBroker with full DB stub."""
        models_stub = types.ModuleType("core.storage.models")

        class FakeField:
            def __gt__(self, o): return MagicMock()
            def __lt__(self, o): return MagicMock()
            def __eq__(self, o): return MagicMock()

        for cls in ["Position", "Trade", "Settings", "Signal",
                    "DecisionLog", "AccountSnapshot"]:
            m = MagicMock()
            m.instrument_id = FakeField()
            m.qty           = FakeField()
            m.side          = FakeField()
            m.ts            = FakeField()
            m.status        = FakeField()
            setattr(models_stub, cls, m)
        sys.modules["core.storage.models"] = models_stub

        bus_stub = types.ModuleType("core.events.bus")
        bus_stub.bus = MagicMock()
        bus_stub.bus.publish = AsyncMock()
        sys.modules["core.events.bus"] = bus_stub

        if "core.execution.paper" in sys.modules:
            del sys.modules["core.execution.paper"]
        try:
            from core.execution.paper import PaperBroker
            return PaperBroker
        except ImportError:
            return None

    def test_paper_broker_importable(self):
        """PaperBroker can be instantiated."""
        PaperBroker = self._load_paper_broker()
        if PaperBroker is None:
            self.skipTest("core.execution.paper not available")
        db = MagicMock()
        db.query.return_value.first.return_value = None
        broker = PaperBroker(db)
        self.assertIsNotNone(broker)

    def test_execute_creates_position(self):
        """execute_signal creates/updates a Position."""
        PaperBroker = self._load_paper_broker()
        if PaperBroker is None:
            self.skipTest("core.execution.paper not available")

        db = MagicMock()
        settings_mock = MagicMock()
        settings_mock.account_balance = Decimal("100000")
        db.query.return_value.first.return_value = settings_mock
        db.query.return_value.filter.return_value.first.return_value = None

        broker = PaperBroker(db)
        signal = _make_signal()

        # Should not raise
        try:
            result = run_async(broker.execute(signal))
            db.commit.assert_called()
        except Exception as e:
            self.fail(f"execute raised unexpectedly: {e}")

    def test_execute_sell_signal(self):
        """SELL signal executes without error."""
        PaperBroker = self._load_paper_broker()
        if PaperBroker is None:
            self.skipTest("core.execution.paper not available")

        db = MagicMock()
        settings_mock = MagicMock()
        settings_mock.account_balance = Decimal("100000")
        db.query.return_value.first.return_value = settings_mock
        db.query.return_value.filter.return_value.first.return_value = None

        broker = PaperBroker(db)
        signal = _make_signal(side="SELL", entry=100.0, sl=105.0, tp=90.0)
        try:
            run_async(broker.execute(signal))
        except Exception as e:
            self.fail(f"execute (SELL) raised unexpectedly: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# P7-02-C  BacktestEngine — end-to-end pipeline
# ══════════════════════════════════════════════════════════════════════════════
class TestBacktestPipeline(unittest.TestCase):

    def _make_strategy(self, name="breakout"):
        from core.strategy.breakout      import BreakoutStrategy
        from core.strategy.mean_reversion import MeanReversionStrategy
        from core.strategy.vwap_bounce    import VWAPBounceStrategy
        return {"breakout": BreakoutStrategy, "mean_reversion": MeanReversionStrategy,
                "vwap_bounce": VWAPBounceStrategy}[name]()

    def _make_candles(self, n=200, seed=42):
        import random
        random.seed(seed)
        candles, price = [], 250.0
        for i in range(n):
            price += random.gauss(0, 0.5)
            price  = max(price, 1.0)
            o, c   = price, price + random.gauss(0, 0.2)
            candles.append({
                "time":   i * 60,
                "open":   o,
                "high":   max(o, c) + abs(random.gauss(0, 0.1)),
                "low":    min(o, c) - abs(random.gauss(0, 0.1)),
                "close":  c,
                "volume": 1000 + random.randint(0, 500),
            })
        return candles

    def test_backtest_runs_without_error(self):
        """BacktestEngine completes without raising."""
        from apps.backtest.engine import BacktestEngine
        engine  = BacktestEngine(self._make_strategy("breakout"), initial_balance=100_000.0)
        candles = self._make_candles(n=200)
        result  = engine.run("TQBR:SBER", candles)
        self.assertIsNotNone(result)

    def test_backtest_result_fields(self):
        """BacktestResult contains required fields."""
        from apps.backtest.engine import BacktestEngine
        engine  = BacktestEngine(self._make_strategy("breakout"), initial_balance=100_000.0)
        result  = engine.run("TQBR:SBER", self._make_candles(200))
        for field in ("total_trades", "win_rate", "profit_factor",
                      "max_drawdown_pct", "total_return_pct", "equity_curve"):
            with self.subTest(field=field):
                self.assertTrue(hasattr(result, field),
                                f"Missing field: {field}")

    def test_win_rate_range(self):
        """win_rate is always in [0, 100]."""
        from apps.backtest.engine import BacktestEngine
        result = BacktestEngine(self._make_strategy("breakout"), initial_balance=100_000.0).run("TQBR:SBER", self._make_candles(200))
        self.assertGreaterEqual(result.win_rate, 0.0)
        self.assertLessEqual(result.win_rate,   100.0)

    def test_max_drawdown_non_negative(self):
        """max_drawdown_pct is always ≥ 0."""
        from apps.backtest.engine import BacktestEngine
        result = BacktestEngine(self._make_strategy("breakout"), initial_balance=100_000.0).run("TQBR:SBER", self._make_candles(200))
        self.assertGreaterEqual(result.max_drawdown_pct, 0.0)

    def test_equity_curve_starts_at_initial_balance(self):
        """equity_curve[0].equity == initial_balance."""
        from apps.backtest.engine import BacktestEngine
        initial = 100_000.0
        result  = BacktestEngine(self._make_strategy("breakout"), initial_balance=initial).run("TQBR:SBER", self._make_candles(200))
        if result.equity_curve:
            self.assertAlmostEqual(result.equity_curve[0]['equity'], initial, delta=1.0)

    def test_equity_curve_monotone_without_trades(self):
        """Flat price → no trades → equity stays constant."""
        from apps.backtest.engine import BacktestEngine
        flat = [{"time": i*60, "open": 100.0, "high": 100.01,
                 "low": 99.99, "close": 100.0, "volume": 1000}
                for i in range(100)]
        result = BacktestEngine(self._make_strategy("breakout"), initial_balance=100_000.0).run("TQBR:SBER", flat)
        if result.total_trades == 0 and len(result.equity_curve) > 1:
            equities = [p['equity'] for p in result.equity_curve]
            self.assertEqual(min(equities), max(equities),
                             "Flat prices: equity should not change without trades")

    def test_all_strategies_run(self):
        """All three strategies execute without raising."""
        from apps.backtest.engine import BacktestEngine
        for strat in ("breakout", "mean_reversion", "vwap_bounce"):
            with self.subTest(strategy=strat):
                result = BacktestEngine(self._make_strategy(strat), initial_balance=100_000.0).run("TQBR:SBER", self._make_candles(200))
                self.assertIsNotNone(result)

    def test_profit_factor_not_negative(self):
        """profit_factor is None or ≥ 0."""
        from apps.backtest.engine import BacktestEngine
        result = BacktestEngine(self._make_strategy("breakout"), initial_balance=100_000.0).run("TQBR:SBER", self._make_candles(300, seed=7))
        if result.profit_factor is not None:
            self.assertGreaterEqual(result.profit_factor, 0.0)

    def test_final_balance_consistent_with_return(self):
        """final_balance ≈ initial × (1 + total_return_pct / 100)."""
        from apps.backtest.engine import BacktestEngine
        initial = 100_000.0
        result  = BacktestEngine(self._make_strategy("breakout"), initial_balance=initial).run("TQBR:SBER", self._make_candles(300))
        expected = initial * (1 + result.total_return_pct / 100)
        self.assertAlmostEqual(result.final_balance, expected, delta=initial * 0.01)

    def test_walk_forward_different_windows_produce_results(self):
        """Walk-forward splits: each segment produces a valid result."""
        from apps.backtest.engine import BacktestEngine
        candles = self._make_candles(300)
        n = len(candles)
        for split in [0.5, 0.7]:
            train_end = int(n * split)
            for seg in [candles[:train_end], candles[train_end:]]:
                if len(seg) > 30:
                    result = BacktestEngine(self._make_strategy("breakout"), initial_balance=100_000.0).run("TQBR:SBER", seg)
                    self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
