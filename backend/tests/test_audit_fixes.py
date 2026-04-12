"""
Verification tests for audit fixes.
Covers critical bugs, logic fixes, and security improvements.

Run: python -m pytest backend/tests/test_audit_fixes.py -v
"""
from __future__ import annotations

import math
import sys
import os
from decimal import Decimal
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─────────────────────────────────────────────────────────────────────────────
# FIX 1.1: DecisionEngine.evaluate() — reasons.extend vs reasons.append
# ─────────────────────────────────────────────────────────────────────────────

def _make_settings(**overrides):
    """Build a mock Settings ORM object with sensible defaults."""
    defaults = {
        "decision_threshold": 70,
        "atr_stop_hard_min": Decimal("0.3"),
        "atr_stop_hard_max": Decimal("5.0"),
        "atr_stop_soft_min": Decimal("0.6"),
        "atr_stop_soft_max": Decimal("2.5"),
        "rr_min": Decimal("1.5"),
        "w_regime": 20,
        "w_volatility": 15,
        "w_momentum": 15,
        "w_levels": 20,
        "w_costs": 15,
        "w_volume": 10,
        "no_trade_opening_minutes": 0,
        "close_before_session_end_minutes": 0,
        "fees_bps": 3,
        "slippage_bps": 5,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_candles(n=100, base_price=270.0, atr_pct=0.01):
    """Generate N test candles with controlled volatility."""
    import random
    random.seed(42)
    candles = []
    price = base_price
    for i in range(n):
        change = (random.random() - 0.5) * base_price * atr_pct
        close = price + change
        high = max(price, close) + abs(change) * 0.3
        low = min(price, close) - abs(change) * 0.3
        candles.append({
            "time": 1700000000 + i * 60,
            "open": round(price, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "close": round(close, 4),
            "volume": 500 + int(random.random() * 1000),
        })
        price = close
    return candles


def test_fix_1_1_evaluate_full_scoring_no_crash():
    """
    FIX 1.1: evaluate() must not crash when scoring functions return list[Reason].
    Before fix: AttributeError in _finalize() because list[Reason] has no .severity.
    """
    from apps.worker.decision_engine.engine import DecisionEngine
    from apps.worker.decision_engine.types import MarketSnapshot, Decision

    settings = _make_settings(
        # Disable session filter for testing
        no_trade_opening_minutes=0,
        close_before_session_end_minutes=0,
    )

    candles = _make_candles(100, base_price=270.0, atr_pct=0.008)

    # Signal that passes hard-reject checks
    signal = MagicMock()
    signal.side = "BUY"
    signal.entry = Decimal("270.5")
    signal.sl = Decimal("268.0")   # 2.5 points stop
    signal.tp = Decimal("274.5")   # 4 points target → R ~1.6
    signal.size = Decimal("10")
    signal.r = Decimal("1.6")

    snapshot = MarketSnapshot(
        candles=candles,
        last_price=Decimal("270.5"),
    )

    de = DecisionEngine(settings)

    # Before fix this would crash with AttributeError
    with patch("apps.worker.decision_engine.rules.check_session", return_value=None):
        result = de.evaluate(signal, snapshot)

    assert result is not None
    assert result.decision in (Decision.TAKE, Decision.SKIP, Decision.REJECT)
    assert 0 <= result.score_pct <= 100
    # All reasons must be Reason instances, not lists
    for reason in result.reasons:
        assert hasattr(reason, "severity"), f"Expected Reason, got {type(reason)}"
        assert hasattr(reason, "code"), f"Expected Reason, got {type(reason)}"


# ─────────────────────────────────────────────────────────────────────────────
# FIX 1.2: AI prompt — safe formatting for None values
# ─────────────────────────────────────────────────────────────────────────────

def test_fix_1_2_prompt_no_crash_on_none():
    """
    FIX 1.2: build_user_prompt must not crash when candles_summary has None values.
    Before fix: ValueError or TypeError on None:.4f formatting.
    """
    from apps.worker.ai.prompts import build_user_prompt
    from apps.worker.ai.types import AIContext

    ctx = AIContext(
        signal_id="sig_test",
        instrument_id="TQBR:SBER",
        side="BUY",
        entry=270.5,
        sl=268.0,
        tp=274.5,
        size=10,
        r=1.6,
        de_score=65,
        de_decision="SKIP",
        de_reasons=[],
        de_metrics={},
        candles_summary={
            "last_close": 270.5,
            "ema50": None,       # can be None
            "atr14": None,       # was wrong key "atr" before fix
            "rsi14": None,       # can be None
            "macd_hist": None,   # always None in _build_candles_summary
        },
    )

    # Before fix this would crash with ValueError/TypeError
    prompt = build_user_prompt(ctx)

    assert isinstance(prompt, str)
    assert "TQBR:SBER" in prompt
    assert "270.5" in prompt
    # Should have N/A for None values, not crash
    assert "N/A" in prompt


def test_fix_1_2_prompt_correct_key_atr14():
    """FIX 1.2: Prompt must use 'atr14' key, not 'atr'."""
    from apps.worker.ai.prompts import build_user_prompt
    from apps.worker.ai.types import AIContext

    ctx = AIContext(
        signal_id="sig_test",
        instrument_id="TQBR:SBER",
        side="BUY",
        entry=270.5, sl=268.0, tp=274.5, size=10, r=1.6,
        de_score=65, de_decision="SKIP",
        de_reasons=[], de_metrics={},
        candles_summary={"last_close": 270.5, "ema50": 269.0, "atr14": 1.5, "rsi14": 55.0, "macd_hist": 0.02},
    )

    prompt = build_user_prompt(ctx)
    # Should contain ATR value, not N/A
    assert "1.5" in prompt
    assert "55.0" in prompt


# ─────────────────────────────────────────────────────────────────────────────
# FIX 5.2: TelegramNotifier.from_settings() alias
# ─────────────────────────────────────────────────────────────────────────────

def test_fix_5_2_telegram_from_settings_exists():
    """FIX 5.2: TelegramNotifier must have from_settings() method."""
    from core.notifications.telegram import TelegramNotifier

    assert hasattr(TelegramNotifier, "from_settings"), \
        "TelegramNotifier.from_settings() method missing — monitor.py and processor.py call it"
    assert hasattr(TelegramNotifier, "from_config"), \
        "TelegramNotifier.from_config() method should still exist"


# ─────────────────────────────────────────────────────────────────────────────
# FIX 5.3: Account router — Trade has no realized_pnl
# ─────────────────────────────────────────────────────────────────────────────

def test_fix_5_3_trade_has_no_realized_pnl():
    """Verify that Trade model does NOT have realized_pnl (it's on Position)."""
    from core.storage.models import Trade, Position

    trade_columns = {c.name for c in Trade.__table__.columns}
    position_columns = {c.name for c in Position.__table__.columns}

    assert "realized_pnl" not in trade_columns, "Trade should not have realized_pnl"
    assert "realized_pnl" in position_columns, "Position should have realized_pnl"


# ─────────────────────────────────────────────────────────────────────────────
# FIX 5.1: Backtest router — Depends import
# ─────────────────────────────────────────────────────────────────────────────

def test_fix_5_1_backtest_router_imports():
    """FIX 5.1: Backtest router must import Depends from fastapi."""
    source_path = os.path.join(os.path.dirname(__file__), "..", "apps", "api", "routers", "backtest.py")
    with open(source_path) as f:
        source = f.read()
    assert "Depends" in source, "backtest.py must import Depends"
    assert "from fastapi import" in source and "Depends" in source


# ─────────────────────────────────────────────────────────────────────────────
# FIX 6: Crypto module
# ─────────────────────────────────────────────────────────────────────────────

def test_fix_6_crypto_module_exists():
    """P8-02: core.security.crypto module must exist and have expected functions."""
    from core.security.crypto import encrypt_token, decrypt_token, is_encrypted

    # Without encryption key, should pass through plaintext
    assert decrypt_token("") == ""
    assert decrypt_token("plain_value") == "plain_value"
    assert not is_encrypted("plain_value")
    assert is_encrypted("enc:v1:something")


# ─────────────────────────────────────────────────────────────────────────────
# INDICATOR TESTS (verify correctness)
# ─────────────────────────────────────────────────────────────────────────────

def test_indicators_ema():
    """Verify EMA calculation with known values."""
    from apps.worker.decision_engine.indicators import calc_ema

    values = [i * 1.0 for i in range(1, 21)]  # 1..20
    ema = calc_ema(values, 10)
    assert ema is not None
    assert 10 < ema < 20  # EMA follows trend but lags


def test_indicators_rsi_extreme():
    """RSI should be 100 when all moves are positive."""
    from apps.worker.decision_engine.indicators import calc_rsi

    values = [float(i) for i in range(100)]  # monotonic rise
    rsi = calc_rsi(values, 14)
    assert rsi is not None
    assert rsi == 100.0


def test_indicators_volume_ratio():
    """Volume ratio should be >1 when current volume exceeds average."""
    from apps.worker.decision_engine.indicators import calc_volume_ratio

    volumes = [100.0] * 21
    volumes[-1] = 200.0  # current is 2x average
    ratio = calc_volume_ratio(volumes, 20)
    assert ratio is not None
    assert abs(ratio - 2.0) < 0.01


# ─────────────────────────────────────────────────────────────────────────────
# RISK MANAGER — correlation parameter
# ─────────────────────────────────────────────────────────────────────────────

def test_fix_2_1_risk_manager_accepts_candles_map():
    """FIX 2.1: check_new_signal must accept candles_map keyword."""
    from core.risk.manager import RiskManager
    import inspect

    sig = inspect.signature(RiskManager.check_new_signal)
    assert "candles_map" in sig.parameters, \
        "check_new_signal must have candles_map parameter for correlation filter"


# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY — basic sanity
# ─────────────────────────────────────────────────────────────────────────────

def test_breakout_strategy_buy_signal():
    """Breakout should generate BUY when close breaks above range high."""
    from core.strategy.breakout import BreakoutStrategy

    candles = _make_candles(30, base_price=270.0, atr_pct=0.005)
    # Force last candle to break above range
    range_high = max(float(c["high"]) for c in candles[:-1])
    candles[-1]["close"] = round(range_high + 0.5, 4)
    candles[-1]["high"] = round(range_high + 0.8, 4)

    strategy = BreakoutStrategy(lookback=20)
    signal = strategy.analyze("TQBR:SBER", candles)

    assert signal is not None
    assert signal["side"] == "BUY"
    assert signal["sl"] < signal["entry"] < signal["tp"]
    assert signal["r"] > 0


def test_mean_reversion_strategy_interface():
    """Mean reversion strategy conforms to BaseStrategy interface."""
    from core.strategy.mean_reversion import MeanReversionStrategy

    s = MeanReversionStrategy()
    assert s.name == "mean_reversion"
    assert s.lookback > 0
    assert hasattr(s, "analyze")


def test_vwap_bounce_strategy_interface():
    """VWAP bounce strategy conforms to BaseStrategy interface."""
    from core.strategy.vwap_bounce import VWAPBounceStrategy

    s = VWAPBounceStrategy()
    assert s.name == "vwap_bounce"
    assert s.lookback > 0
    assert hasattr(s, "analyze")


# ─────────────────────────────────────────────────────────────────────────────
# SETTINGS SCHEMA — new fields exist
# ─────────────────────────────────────────────────────────────────────────────

def test_fix_4_1_risk_settings_schema_has_new_fields():
    """FIX 4.1: RiskSettings schema must have session/correlation/AI fields."""
    from core.models.schemas import RiskSettings

    fields = set(RiskSettings.model_fields.keys())
    # Session
    assert "no_trade_opening_minutes" in fields
    assert "higher_timeframe" in fields
    # Correlation
    assert "correlation_threshold" in fields
    assert "max_correlated_positions" in fields
    # AI chain
    assert "ai_primary_provider" in fields
    assert "ai_fallback_providers" in fields


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
