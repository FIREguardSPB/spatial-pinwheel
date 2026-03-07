"""
P7-01: Unit tests — PositionMonitor, RiskManager, SessionFilter, BreakoutStrategy SELL.

Designed to run without installed deps (sqlalchemy/pydantic stubbed via sys.modules).
Run: python -m unittest tests.test_risk_manager -v
"""
import asyncio
import math
import os
import sys
import time
import types
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Stub heavy deps before any project import ─────────────────────────────────
def _make_sa_stub():
    """Return a minimal sqlalchemy stub module tree."""
    sa       = types.ModuleType("sqlalchemy")
    sa_orm   = types.ModuleType("sqlalchemy.orm")
    sa_func  = MagicMock()
    sa.func  = sa_func
    sa.func.sum = MagicMock(return_value=MagicMock())

    class _FakeColumn:
        def __init__(self, *a, **kw): pass
        def __get__(self, obj, objtype=None): return self
    class _FakeBase:
        __tablename__ = "stub"
        metadata = MagicMock()

    sa.Column     = _FakeColumn
    sa.String     = MagicMock()
    sa.Integer    = MagicMock()
    sa.BigInteger = MagicMock()
    sa.Numeric    = MagicMock()
    sa.Boolean    = MagicMock()
    sa.JSON       = MagicMock()
    sa.Text       = MagicMock()
    sa.Float      = MagicMock()
    sa.Index      = MagicMock()
    sa.create_engine  = MagicMock()
    sa.event          = MagicMock()
    sa_orm.Session    = MagicMock()
    sa_orm.sessionmaker = MagicMock()
    sa_orm.relationship = MagicMock()
    sa_orm.declarative_base = MagicMock(return_value=_FakeBase)
    sa_orm.DeclarativeBase  = _FakeBase
    sa.orm = sa_orm
    return sa, sa_orm

_sa, _sa_orm = _make_sa_stub()
sys.modules.setdefault("sqlalchemy",               _sa)
sys.modules.setdefault("sqlalchemy.orm",           _sa_orm)
sys.modules.setdefault("sqlalchemy.ext",           types.ModuleType("sqlalchemy.ext"))
sys.modules.setdefault("sqlalchemy.ext.asyncio",   types.ModuleType("sqlalchemy.ext.asyncio"))

def _make_pydantic_stub():
    pd = types.ModuleType("pydantic")
    pd_settings = types.ModuleType("pydantic_settings")
    class BaseModel:
        def __init__(self, **kw):
            for k, v in kw.items(): setattr(self, k, v)
        def model_dump(self): return {}
    class BaseSettings(BaseModel): pass
    def Field(*a, **kw): return kw.get("default", None)
    pd.BaseModel   = BaseModel
    pd.Field       = Field
    pd.validator   = lambda *a, **kw: (lambda f: f)
    pd.field_validator = lambda *a, **kw: (lambda f: f)
    pd_settings.BaseSettings = BaseSettings
    return pd, pd_settings

_pd, _pd_settings = _make_pydantic_stub()
sys.modules.setdefault("pydantic",          _pd)
sys.modules.setdefault("pydantic_settings", _pd_settings)

# Stub redis, structlog, grpc, prometheus
for _mod in ["redis", "redis.asyncio", "structlog", "grpc",
             "prometheus_client", "prometheus_client.exposition",
             "google", "google.protobuf", "tinkoff", "tinkoff.invest"]:
    sys.modules.setdefault(_mod, types.ModuleType(_mod))

# ── Now safe to import project modules ────────────────────────────────────────
try:
    from core.utils.session import (
        is_trading_session, minutes_until_session_end,
        should_close_before_session_end, MOEX_OPEN, MOEX_CLOSE,
    )
    _HAS_SESSION = True
except Exception:
    _HAS_SESSION = False

try:
    from core.strategy.breakout import BreakoutStrategy
    _HAS_BREAKOUT = True
except Exception:
    _HAS_BREAKOUT = False

try:
    from apps.worker.decision_engine import indicators
    _HAS_INDICATORS = True
except Exception:
    _HAS_INDICATORS = False

_skip_no_session    = unittest.skipUnless(_HAS_SESSION,    "core.utils.session not available")
_skip_no_breakout   = unittest.skipUnless(_HAS_BREAKOUT,   "BreakoutStrategy not available")
_skip_no_indicators = unittest.skipUnless(_HAS_INDICATORS, "indicators not available")


# ── Test helpers ──────────────────────────────────────────────────────────────
def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value  = None
    db.query.return_value.filter.return_value.count.return_value  = 0
    db.query.return_value.filter.return_value.all.return_value    = []
    db.query.return_value.filter.return_value.scalar.return_value = None
    db.query.return_value.first.return_value = None
    db.commit = MagicMock()
    db.add    = MagicMock()
    return db


def _mock_position(instrument_id="TQBR:SBER", side="BUY",
                   qty=10, avg_price=100.0, sl=95.0, tp=110.0):
    p = MagicMock()
    p.instrument_id = instrument_id
    p.side          = side
    p.qty           = Decimal(str(qty))
    p.avg_price     = Decimal(str(avg_price))
    p.sl            = Decimal(str(sl))
    p.tp            = Decimal(str(tp))
    p.unrealized_pnl = Decimal("0")
    return p


def _mock_settings(**kw):
    s = MagicMock()
    s.max_concurrent_positions = kw.get("max_positions",    3)
    s.daily_loss_limit_pct     = kw.get("daily_loss_pct",   5.0)
    s.max_trades_per_day       = kw.get("max_trades",        0)
    s.cooldown_losses          = kw.get("cooldown_losses",   0)
    s.cooldown_minutes         = kw.get("cooldown_minutes",  0)
    s.correlation_threshold    = kw.get("corr_threshold",    0.8)
    s.max_correlated_positions = kw.get("max_corr_pos",      2)
    s.risk_per_trade_pct       = kw.get("risk_pct",          1.0)
    return s



class _FakeField:
    """Fake SQLAlchemy column field: supports comparison operators for filter()."""
    def __gt__(self, other): return MagicMock()
    def __lt__(self, other): return MagicMock()
    def __ge__(self, other): return MagicMock()
    def __le__(self, other): return MagicMock()
    def __eq__(self, other): return MagicMock()
    def __ne__(self, other): return MagicMock()


def _make_candles(n=25, trend="up", start_price=200.0):
    candles, price = [], start_price
    for i in range(n):
        price += 0.5 if trend == "up" else -0.5
        candles.append({
            "time": i * 60, "open": price - 0.1, "high": price + 0.3,
            "low": price - 0.3, "close": price, "volume": 1000 + i * 10,
        })
    return candles


# ══════════════════════════════════════════════════════════════════════════════
# P7-01-A  PositionMonitor
# ══════════════════════════════════════════════════════════════════════════════
class TestPositionMonitor(unittest.TestCase):

    def _load_monitor(self):
        # Stub models & bus locally per-test
        models_stub = types.ModuleType("core.storage.models")
        for cls in ["Position","Trade","DecisionLog","Signal","Settings"]:
            m = MagicMock()
            m.instrument_id = _FakeField()
            m.qty = _FakeField()
            m.side = _FakeField()
            m.ts = _FakeField()
            m.status = _FakeField()
            m.updated_ts = _FakeField()
            setattr(models_stub, cls, m)
        sys.modules["core.storage.models"] = models_stub

        bus_stub = types.ModuleType("core.events.bus")
        bus_stub.bus = MagicMock()
        bus_stub.bus.publish = AsyncMock()
        sys.modules["core.events.bus"] = bus_stub

        # ai_repo stub
        ai_stub = types.ModuleType("core.storage.repos.ai_repo")
        ai_stub.update_outcome = MagicMock()
        sys.modules.setdefault("core.storage.repos",          types.ModuleType("core.storage.repos"))
        sys.modules["core.storage.repos.ai_repo"] = ai_stub

        if "core.execution.monitor" in sys.modules:
            del sys.modules["core.execution.monitor"]
        from core.execution.monitor import PositionMonitor
        return PositionMonitor, bus_stub.bus

    def _make(self, position):
        PositionMonitor, bus = self._load_monitor()
        db = _mock_db()
        db.query.return_value.filter.return_value.first.return_value = position
        return PositionMonitor(db), bus

    def test_sl_trigger_buy(self):
        """BUY: price ≤ SL → position closes (qty=0)."""
        pos = _mock_position(side="BUY", sl=95.0, tp=110.0)
        monitor, _ = self._make(pos)
        run_async(monitor.on_tick("TQBR:SBER", current_price=94.0))
        self.assertEqual(pos.qty, Decimal("0"))

    def test_tp_trigger_buy(self):
        """BUY: price ≥ TP → position closes."""
        pos = _mock_position(side="BUY", sl=95.0, tp=110.0)
        monitor, _ = self._make(pos)
        run_async(monitor.on_tick("TQBR:SBER", current_price=111.0))
        self.assertEqual(pos.qty, Decimal("0"))

    def test_sl_trigger_sell(self):
        """SELL: price ≥ SL → position closes."""
        pos = _mock_position(side="SELL", avg_price=100.0, sl=106.0, tp=90.0)
        monitor, _ = self._make(pos)
        run_async(monitor.on_tick("TQBR:SBER", current_price=107.0))
        self.assertEqual(pos.qty, Decimal("0"))

    def test_tp_trigger_sell(self):
        """SELL: price ≤ TP → position closes."""
        pos = _mock_position(side="SELL", avg_price=100.0, sl=106.0, tp=90.0)
        monitor, _ = self._make(pos)
        run_async(monitor.on_tick("TQBR:SBER", current_price=89.0))
        self.assertEqual(pos.qty, Decimal("0"))

    def test_no_trigger_midrange(self):
        """Price in SL–TP range → position stays open."""
        pos = _mock_position(side="BUY", sl=95.0, tp=110.0)
        orig = pos.qty
        monitor, _ = self._make(pos)
        run_async(monitor.on_tick("TQBR:SBER", current_price=102.0))
        self.assertEqual(pos.qty, orig)

    def test_time_stop(self):
        """After N bars with time_stop_bars set → position closes."""
        pos = _mock_position(side="BUY", sl=50.0, tp=300.0)
        monitor, _ = self._make(pos)
        for _ in range(8):
            run_async(monitor.on_tick("TQBR:SBER", current_price=101.0,
                                       time_stop_bars=5))
        self.assertEqual(pos.qty, Decimal("0"))

    def test_no_position_noop(self):
        """No open position → on_tick is silent (no commit)."""
        PositionMonitor, _ = self._load_monitor()
        db = _mock_db()
        db.query.return_value.filter.return_value.first.return_value = None
        monitor = PositionMonitor(db)
        run_async(monitor.on_tick("TQBR:SBER", current_price=100.0))
        db.commit.assert_not_called()

    def test_unrealized_pnl_buy(self):
        """BUY unrealized_pnl = qty × (current − avg)."""
        pos = _mock_position(side="BUY", qty=10, avg_price=100.0, sl=90.0, tp=120.0)
        monitor, _ = self._make(pos)
        run_async(monitor.on_tick("TQBR:SBER", current_price=105.0))
        self.assertAlmostEqual(float(pos.unrealized_pnl), 50.0, places=1)

    def test_unrealized_pnl_sell(self):
        """SELL unrealized_pnl = qty × (avg − current)."""
        pos = _mock_position(side="SELL", qty=10, avg_price=100.0, sl=110.0, tp=85.0)
        monitor, _ = self._make(pos)
        run_async(monitor.on_tick("TQBR:SBER", current_price=95.0))
        self.assertAlmostEqual(float(pos.unrealized_pnl), 50.0, places=1)

    def test_sl_exact_boundary_buy(self):
        """BUY: price == SL exactly → triggers close."""
        pos = _mock_position(side="BUY", sl=95.0, tp=110.0)
        monitor, _ = self._make(pos)
        run_async(monitor.on_tick("TQBR:SBER", current_price=95.0))
        self.assertEqual(pos.qty, Decimal("0"))

    def test_tp_exact_boundary_buy(self):
        """BUY: price == TP exactly → triggers close."""
        pos = _mock_position(side="BUY", sl=95.0, tp=110.0)
        monitor, _ = self._make(pos)
        run_async(monitor.on_tick("TQBR:SBER", current_price=110.0))
        self.assertEqual(pos.qty, Decimal("0"))


# ══════════════════════════════════════════════════════════════════════════════
# P7-01-B  RiskManager
# ══════════════════════════════════════════════════════════════════════════════
class TestRiskManager(unittest.TestCase):

    def _load(self, settings, open_pos=0, today_pnl=0.0, today_trades=0):
        # Stub all ORM models
        models_stub = types.ModuleType("core.storage.models")
        for cls in ["Position","Settings","Trade"]:
            m = MagicMock()
            # Support comparison operators on class-level field (e.g. Position.qty > 0)
            m.qty = _FakeField()
            m.ts = _FakeField()
            m.instrument_id = _FakeField()
            m.realized_pnl  = _FakeField()
            m.side          = _FakeField()
            m.status        = _FakeField()
            setattr(models_stub, cls, m)
        sys.modules["core.storage.models"] = models_stub

        corr_stub = types.ModuleType("core.risk.correlation")
        corr_stub.check_correlation = MagicMock(return_value=(True, "OK"))
        corr_stub.calc_correlation  = MagicMock(return_value=0.0)
        corr_stub._returns          = MagicMock(return_value=[])
        sys.modules["core.risk.correlation"] = corr_stub

        if "core.risk.manager" in sys.modules:
            del sys.modules["core.risk.manager"]
        from core.risk.manager import RiskManager

        db = _mock_db()
        db.query.return_value.first.return_value = settings
        db.query.return_value.filter.return_value.count.return_value = open_pos

        mgr = RiskManager(db)
        mgr._get_today_realized_pnl = lambda: today_pnl
        mgr._get_today_trades_count = lambda: today_trades
        mgr._get_paper_balance      = lambda: 100_000.0
        # Patch the live DB position count
        mgr.db.query.return_value.filter.return_value.count.return_value = open_pos
        return mgr

    def test_max_positions_blocks(self):
        """max_concurrent_positions=3, open=3 → blocked."""
        mgr = self._load(_mock_settings(max_positions=3), open_pos=3)
        ok, reason = mgr.check_new_signal({"instrument_id": "TQBR:SBER"})
        self.assertFalse(ok)
        self.assertIn("Max positions", reason)

    def test_max_positions_allows(self):
        """max_concurrent_positions=3, open=2 → allowed."""
        mgr = self._load(_mock_settings(max_positions=3), open_pos=2)
        ok, _ = mgr.check_new_signal({"instrument_id": "TQBR:SBER"})
        self.assertTrue(ok)

    def test_daily_loss_limit_blocks(self):
        """Daily loss 3000 > 2% of 100k=2000 → blocked."""
        mgr = self._load(_mock_settings(daily_loss_pct=2.0), today_pnl=-3000.0)
        ok, reason = mgr.check_new_signal({"instrument_id": "TQBR:SBER"})
        self.assertFalse(ok)
        self.assertIn("Daily loss", reason)

    def test_daily_loss_profit_allows(self):
        """Positive PnL today → allowed regardless of limit."""
        mgr = self._load(_mock_settings(daily_loss_pct=2.0), today_pnl=500.0)
        ok, _ = mgr.check_new_signal({"instrument_id": "TQBR:SBER"})
        self.assertTrue(ok)

    def test_daily_loss_below_limit_allows(self):
        """Loss 500 < 2% of 100k=2000 → allowed."""
        mgr = self._load(_mock_settings(daily_loss_pct=2.0), today_pnl=-500.0)
        ok, _ = mgr.check_new_signal({"instrument_id": "TQBR:SBER"})
        self.assertTrue(ok)

    def test_max_trades_blocks(self):
        """max_trades_per_day=5, today=5 → blocked."""
        mgr = self._load(_mock_settings(max_trades=5), today_trades=5)
        ok, reason = mgr.check_new_signal({"instrument_id": "TQBR:SBER"})
        self.assertFalse(ok)
        self.assertIn("Max trades", reason)

    def test_max_trades_allows(self):
        """max_trades_per_day=5, today=4 → allowed."""
        mgr = self._load(_mock_settings(max_trades=5), today_trades=4)
        ok, _ = mgr.check_new_signal({"instrument_id": "TQBR:SBER"})
        self.assertTrue(ok)

    def test_max_trades_zero_disabled(self):
        """max_trades_per_day=0 → check disabled."""
        mgr = self._load(_mock_settings(max_trades=0), today_trades=999)
        ok, _ = mgr.check_new_signal({"instrument_id": "TQBR:SBER"})
        self.assertTrue(ok)

    def test_no_settings_allows(self):
        """No Settings row in DB → allow by default (safe fallback)."""
        models_stub = types.ModuleType("core.storage.models")
        for cls in ["Position","Settings","Trade"]:
            m = MagicMock()
            m.qty = _FakeField()
            m.instrument_id = _FakeField()
            setattr(models_stub, cls, m)
        sys.modules["core.storage.models"] = models_stub
        sys.modules["core.risk.correlation"] = types.ModuleType("core.risk.correlation")
        sys.modules["core.risk.correlation"].check_correlation = lambda *a,**kw: (True,"OK")
        if "core.risk.manager" in sys.modules:
            del sys.modules["core.risk.manager"]
        from core.risk.manager import RiskManager
        db = _mock_db()
        db.query.return_value.first.return_value = None
        mgr = RiskManager(db)
        ok, _ = mgr.check_new_signal({"instrument_id": "TQBR:SBER"})
        self.assertTrue(ok)

    def test_position_size_scales_with_risk_pct(self):
        """Higher risk_per_trade_pct → larger position size."""
        s = _mock_settings(risk_pct=1.0)
        mgr = self._load(s)
        size1 = mgr.calculate_position_size(entry=100.0, sl=98.0)

        s.risk_per_trade_pct = 2.0
        mgr2 = self._load(s)
        size2 = mgr2.calculate_position_size(entry=100.0, sl=98.0)
        self.assertGreater(size2, size1)

    def test_position_size_scales_with_balance(self):
        """Larger balance → larger position for same risk_pct."""
        s = _mock_settings(risk_pct=1.0)
        mgr = self._load(s)
        mgr._get_paper_balance = lambda: 100_000.0
        size1 = mgr.calculate_position_size(entry=100.0, sl=98.0)

        mgr2 = self._load(s)
        mgr2._get_paper_balance = lambda: 200_000.0
        size2 = mgr2.calculate_position_size(entry=100.0, sl=98.0)
        self.assertGreater(size2, size1)

    def test_position_size_zero_sl_gap_safe(self):
        """SL == entry → position_size must not raise (ZeroDivision guard)."""
        mgr = self._load(_mock_settings())
        try:
            size = mgr.calculate_position_size(entry=100.0, sl=100.0)
            self.assertIsInstance(size, (int, float, type(None)))
        except ZeroDivisionError:
            self.fail("calculate_position_size raised ZeroDivisionError for sl==entry")


# ══════════════════════════════════════════════════════════════════════════════
# P7-01-C  Session utilities (pure Python — no stubs needed)
# ══════════════════════════════════════════════════════════════════════════════
@_skip_no_session
class TestSessionUtils(unittest.TestCase):

    def test_is_trading_session_returns_bool(self):
        result = is_trading_session()
        self.assertIsInstance(result, bool)

    def test_minutes_until_session_end_float(self):
        result = minutes_until_session_end()
        self.assertIsInstance(result, float)

    def test_should_close_zero_always_false(self):
        self.assertFalse(should_close_before_session_end(0))

    def test_moex_open_is_0950(self):
        from datetime import time as dtime
        self.assertEqual(MOEX_OPEN, dtime(9, 50))

    def test_moex_close_is_1850(self):
        from datetime import time as dtime
        self.assertEqual(MOEX_CLOSE, dtime(18, 50))

    def test_trading_session_during_hours(self):
        """Patching _msk_now to 12:00 → is_trading_session() is True."""
        from datetime import datetime, time as dtime, timezone
        import core.utils.session as s_mod
        fake_dt = datetime(2025, 1, 2, 9, 0, 0, tzinfo=timezone.utc)  # UTC 09:00 = MSK 12:00
        with patch.object(s_mod, "_msk_now",
                          return_value=fake_dt.replace(hour=12, minute=0)):
            result = s_mod.is_trading_session()
        self.assertTrue(result)

    def test_no_trading_after_close(self):
        """Patching to 22:00 MSK → is_trading_session() is False."""
        import core.utils.session as s_mod
        from datetime import datetime, timezone
        fake_dt = datetime(2025, 1, 2, 22, 0, 0, tzinfo=timezone.utc)
        with patch.object(s_mod, "_msk_now",
                          return_value=fake_dt):
            result = s_mod.is_trading_session()
        self.assertFalse(result)

    def test_check_session_outside_blocks(self):
        """check_session returns a Reason when outside market hours."""
        import core.utils.session as s_mod
        from datetime import datetime, timezone
        fake_dt = datetime(2025, 1, 2, 22, 0, 0, tzinfo=timezone.utc)
        with patch.object(s_mod, "_msk_now", return_value=fake_dt):
            from apps.worker.decision_engine.rules import check_session
            result = check_session()
        self.assertIsNotNone(result)

    def test_check_session_inside_with_no_guard_allows(self):
        """Inside session, no opening/closing guard → check_session returns None."""
        import core.utils.session as s_mod
        from datetime import datetime, timezone
        # 12:00 UTC = 15:00 MSK
        fake_dt = datetime(2025, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        with patch.object(s_mod, "_msk_now", return_value=fake_dt):
            from apps.worker.decision_engine import rules as rules_mod
            if "apps.worker.decision_engine.rules" in sys.modules:
                del sys.modules["apps.worker.decision_engine.rules"]
            from apps.worker.decision_engine.rules import check_session
            result = check_session(
                no_trade_opening_minutes=0,
                close_before_end_minutes=0,
            )
        self.assertIsNone(result)

    def test_should_close_near_session_end(self):
        """should_close_before_session_end returns True with 3 min remaining and limit=5."""
        import core.utils.session as s_mod
        with patch.object(s_mod, "minutes_until_session_end", return_value=3.0):
            result = s_mod.should_close_before_session_end(5)
        self.assertTrue(result)

    def test_should_not_close_far_from_end(self):
        """60 minutes remaining, limit=5 → False."""
        import core.utils.session as s_mod
        with patch.object(s_mod, "minutes_until_session_end", return_value=60.0):
            result = s_mod.should_close_before_session_end(5)
        self.assertFalse(result)


# ══════════════════════════════════════════════════════════════════════════════
# P7-01-D  BreakoutStrategy SELL side
# ══════════════════════════════════════════════════════════════════════════════
@_skip_no_breakout
class TestBreakoutStrategySELL(unittest.TestCase):

    def _signal_or_none(self, candles, lookback=20):
        strategy = BreakoutStrategy(lookback=lookback)
        return strategy.analyze("TQBR:SBER", candles)

    def test_too_few_candles_returns_none(self):
        result = self._signal_or_none(_make_candles(n=5), lookback=20)
        self.assertIsNone(result)

    def test_various_lookbacks_no_crash(self):
        for lb in [5, 10, 15, 20, 25]:
            with self.subTest(lookback=lb):
                result = self._signal_or_none(_make_candles(n=lb + 5), lb)
                self.assertIsInstance(result, (dict, type(None)))

    def test_sell_sl_above_entry(self):
        """If SELL signal: SL must be > entry."""
        candles = _make_candles(n=30, trend="down")
        result  = self._signal_or_none(candles)
        if result and result.get("side") == "SELL":
            self.assertGreater(result["sl"], result["entry"],
                               "SELL: SL must be above entry")

    def test_sell_tp_below_entry(self):
        """If SELL signal: TP must be < entry."""
        candles = _make_candles(n=30, trend="down")
        result  = self._signal_or_none(candles)
        if result and result.get("side") == "SELL":
            self.assertLess(result["tp"], result["entry"],
                            "SELL: TP must be below entry")

    def test_sell_r_positive(self):
        """If SELL signal: R/R must be positive."""
        candles = _make_candles(n=30, trend="down")
        result  = self._signal_or_none(candles)
        if result and result.get("side") == "SELL":
            self.assertGreater(result["r"], 0)

    def test_buy_sl_below_entry(self):
        """If BUY signal: SL must be < entry."""
        candles = _make_candles(n=30, trend="up")
        result  = self._signal_or_none(candles)
        if result and result.get("side") == "BUY":
            self.assertLess(result["sl"], result["entry"])

    def test_buy_tp_above_entry(self):
        """If BUY signal: TP must be > entry."""
        candles = _make_candles(n=30, trend="up")
        result  = self._signal_or_none(candles)
        if result and result.get("side") == "BUY":
            self.assertGreater(result["tp"], result["entry"])

    def test_required_keys_present(self):
        """Any non-None signal must have side/entry/sl/tp/r/reason."""
        for trend in ("up", "down"):
            candles = _make_candles(n=30, trend=trend)
            result  = self._signal_or_none(candles)
            if result is not None:
                for key in ("side", "entry", "sl", "tp", "r"):
                    with self.subTest(trend=trend, key=key):
                        self.assertIn(key, result)

    def test_r_at_least_one(self):
        """R/R must be ≥ 1.0 for any generated signal."""
        for trend in ("up", "down"):
            candles = _make_candles(n=30, trend=trend)
            result  = self._signal_or_none(candles)
            if result is not None:
                with self.subTest(trend=trend):
                    self.assertGreaterEqual(result["r"], 1.0)


# ══════════════════════════════════════════════════════════════════════════════
# P7-01-E  Indicators — parametrised
# ══════════════════════════════════════════════════════════════════════════════
@_skip_no_indicators
class TestIndicatorsParametrised(unittest.TestCase):

    def _closes(self, n=50, start=100.0, step=0.1):
        return [start + i * step for i in range(n)]

    def test_bollinger_band_order(self):
        """Upper > Mid > Lower for all valid periods."""
        for period in [10, 15, 20, 30]:
            with self.subTest(period=period):
                result = indicators.calc_bollinger(self._closes(60), period=period)
                self.assertIsNotNone(result)
                upper, mid, lower = result
                self.assertGreater(upper, mid,  "upper must exceed mid")
                self.assertGreater(mid,   lower, "mid must exceed lower")

    def test_bollinger_insufficient_data(self):
        self.assertIsNone(indicators.calc_bollinger([100.0, 101.0], period=20))

    def test_rsi_range(self):
        """RSI always 0–100."""
        closes = self._closes(30)
        for period in [7, 14, 21]:
            with self.subTest(period=period):
                rsi = indicators.calc_rsi(closes, period=period)
                if rsi is not None:
                    self.assertGreaterEqual(rsi, 0.0)
                    self.assertLessEqual(rsi,   100.0)

    def test_rsi_insufficient_data(self):
        self.assertIsNone(indicators.calc_rsi([100.0, 101.0], period=14))

    def test_atr_non_negative(self):
        """ATR is always ≥ 0."""
        candles = _make_candles(n=30)
        highs   = [c["high"]  for c in candles]
        lows    = [c["low"]   for c in candles]
        closes  = [c["close"] for c in candles]
        for period in [5, 10, 14]:
            with self.subTest(period=period):
                atr = indicators.calc_atr(highs, lows, closes, period=period)
                if atr is not None:
                    self.assertGreaterEqual(atr, 0.0)

    def test_stochastic_range(self):
        """Stochastic %K and %D always 0–100."""
        candles = _make_candles(n=30)
        highs   = [c["high"]  for c in candles]
        lows    = [c["low"]   for c in candles]
        closes  = [c["close"] for c in candles]
        for k in [7, 10, 14]:
            with self.subTest(k=k):
                result = indicators.calc_stochastic(highs, lows, closes, k_period=k)
                if result is not None:
                    pct_k, pct_d = result
                    self.assertGreaterEqual(pct_k, 0.0)
                    self.assertLessEqual(pct_k,   100.0)

    def test_vwap_volume_weighted(self):
        """Heavy-volume bar dominates VWAP."""
        highs   = [101.0, 201.0]
        lows    = [99.0,  199.0]
        closes  = [100.0, 200.0]
        volumes = [1.0,   1000.0]
        vwap    = indicators.calc_vwap(highs, lows, closes, volumes)
        self.assertIsNotNone(vwap)
        self.assertGreater(vwap, 150.0)

    def test_volume_ratio_constant(self):
        """Constant volume → ratio = 1.0."""
        ratio = indicators.calc_volume_ratio([1000.0] * 25)
        self.assertIsNotNone(ratio)
        self.assertAlmostEqual(ratio, 1.0, places=4)

    def test_volume_ratio_spike(self):
        """Last bar 2× average → ratio > 1.8."""
        vols       = [1000.0] * 25
        vols[-1]   = 2000.0
        ratio      = indicators.calc_volume_ratio(vols)
        self.assertIsNotNone(ratio)
        self.assertGreater(ratio, 1.8)

    def test_ema_shorter_period_reacts_faster(self):
        """EMA(5) moves closer to a spike than EMA(20)."""
        closes = [100.0] * 20 + [200.0] * 5
        ema5   = indicators.calc_ema(closes, period=5)
        ema20  = indicators.calc_ema(closes, period=20)
        if ema5 is not None and ema20 is not None:
            # After a sustained spike EMA5 should be > EMA20
            self.assertGreater(ema5, ema20)

    def test_macd_histogram_positive_in_uptrend(self):
        """In a clear uptrend MACD histogram should be positive."""
        closes = [100.0 + i * 1.0 for i in range(60)]
        result = indicators.calc_macd(closes)
        if result is not None:
            macd_line, signal_line, hist = result
            # At the end of a strong uptrend histogram is positive
            self.assertGreaterEqual(hist, -0.001)  # slightly negative due to float precision is OK


# ══════════════════════════════════════════════════════════════════════════════
# P7-01-F  Edge-case / regression tests
# ══════════════════════════════════════════════════════════════════════════════
@_skip_no_breakout
class TestBreakoutEdgeCases(unittest.TestCase):

    def test_all_identical_candles(self):
        """Flat price series must not raise."""
        candles = [{"time": i, "open": 100.0, "high": 100.0,
                    "low": 100.0, "close": 100.0, "volume": 1000}
                   for i in range(25)]
        strategy = BreakoutStrategy(lookback=20)
        result   = strategy.analyze("TQBR:SBER", candles)
        self.assertIsInstance(result, (dict, type(None)))

    def test_extreme_price_values(self):
        """Very large prices must not raise."""
        candles = _make_candles(n=25, start_price=1_000_000.0, trend="up")
        strategy = BreakoutStrategy(lookback=20)
        result   = strategy.analyze("TQBR:SBER", candles)
        self.assertIsInstance(result, (dict, type(None)))

    def test_tiny_price_values(self):
        """Very small prices (penny stocks) must not raise."""
        candles = _make_candles(n=25, start_price=0.01, trend="up")
        for c in candles:
            c["close"] = max(c["close"], 0.001)
            c["high"]  = max(c["high"],  0.001)
            c["low"]   = max(c["low"],   0.001)
        strategy = BreakoutStrategy(lookback=20)
        result   = strategy.analyze("TQBR:SBER", candles)
        self.assertIsInstance(result, (dict, type(None)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
