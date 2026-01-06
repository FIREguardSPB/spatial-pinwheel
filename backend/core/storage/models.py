from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    BigInteger,
    Text,
    Index,
    Numeric,
)
from sqlalchemy.dialects.postgresql import JSONB
from core.storage.database import Base
import datetime


# Helper for UTC (optional use)
def now_utc_ms():
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    risk_profile = Column(String, default="balanced")
    risk_per_trade_pct = Column(Numeric(5, 2), default=1.0)
    daily_loss_limit_pct = Column(Numeric(5, 2), default=2.0)
    max_concurrent_positions = Column(Integer, default=3)
    max_trades_per_day = Column(Integer, default=8)
    rr_target = Column(Numeric(5, 2), default=1.5)
    time_stop_bars = Column(Integer, default=6)
    close_before_session_end_minutes = Column(Integer, default=10)
    cooldown_losses = Column(Integer, default=2)
    cooldown_minutes = Column(Integer, default=60)

    # Decision Engine / Risk
    trade_mode = Column(String, default="review")  # review, auto_paper, auto_live
    decision_engine_enabled = Column(Boolean, default=True)
    decision_threshold = Column(Integer, default=70)

    # Decision Thresholds (P0.2)
    rr_min = Column(Numeric(5, 2), default=1.5)
    atr_stop_hard_min = Column(Numeric(5, 2), default=0.3)
    atr_stop_hard_max = Column(Numeric(5, 2), default=5.0)
    atr_stop_soft_min = Column(Numeric(5, 2), default=0.6)
    atr_stop_soft_max = Column(Numeric(5, 2), default=2.5)

    # Weights (P7 Autotrading Strictness)
    w_regime = Column(Integer, default=20)
    w_volatility = Column(Integer, default=15)
    w_momentum = Column(Integer, default=15)
    w_levels = Column(Integer, default=20)
    w_costs = Column(Integer, default=15)
    w_liquidity = Column(Integer, default=5)  # Reduced from 15 (Stub)

    fees_bps = Column(Integer, default=3)  # default 0.03%
    slippage_bps = Column(Integer, default=5)  # default 0.05%

    updated_ts = Column(BigInteger, default=now_utc_ms, onupdate=now_utc_ms)


class Signal(Base):
    __tablename__ = "signals"

    id = Column(String, primary_key=True)
    instrument_id = Column(String, nullable=False)  # TQBR:SBER (UI only)
    broker_id = Column(String, nullable=True)  # FIGI / UID
    ts = Column(BigInteger, nullable=False)
    side = Column(String, nullable=False)
    entry = Column(Numeric(18, 9), nullable=False)
    sl = Column(Numeric(18, 9), nullable=False)
    tp = Column(Numeric(18, 9), nullable=False)
    size = Column(Numeric(18, 9), nullable=False)
    r = Column(Numeric(18, 9), nullable=False)  # Risk amount
    status = Column(String, nullable=False, default="pending_review")
    reason = Column(Text, nullable=True)
    meta = Column(JSONB, default={})
    created_ts = Column(BigInteger, default=now_utc_ms)
    updated_ts = Column(BigInteger, default=now_utc_ms, onupdate=now_utc_ms)

    # Index: instrument, status, ts
    __table_args__ = (Index("idx_signals_lookup", "instrument_id", "status", "ts"),)


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String, primary_key=True)
    instrument_id = Column(String, nullable=False)
    broker_id = Column(String, nullable=True)  # FIGI / UID
    ts = Column(BigInteger, nullable=False)
    side = Column(String, nullable=False)
    type = Column(String, nullable=False)
    price = Column(Numeric(18, 9), nullable=True)
    qty = Column(Numeric(18, 9), nullable=False)
    filled_qty = Column(Numeric(18, 9), default=0.0)
    status = Column(String, nullable=False)
    related_signal_id = Column(String, unique=True, nullable=True)  # Idempotency
    created_ts = Column(BigInteger, default=now_utc_ms)
    updated_ts = Column(BigInteger, default=now_utc_ms, onupdate=now_utc_ms)


class Trade(Base):
    __tablename__ = "trades"

    trade_id = Column(String, primary_key=True)
    instrument_id = Column(String, nullable=False)
    broker_id = Column(String, nullable=True)  # FIGI / UID
    ts = Column(BigInteger, nullable=False)
    side = Column(String, nullable=False)
    price = Column(Numeric(18, 9), nullable=False)
    qty = Column(Numeric(18, 9), nullable=False)
    order_id = Column(String, nullable=False)

    __table_args__ = (Index("idx_trades_instrument_ts", "instrument_id", "ts"),)


class Position(Base):
    __tablename__ = "positions"

    instrument_id = Column(String, primary_key=True)
    broker_id = Column(String, nullable=True)  # FIGI / UID
    side = Column(String, nullable=False)
    qty = Column(Numeric(18, 9), default=0.0)
    avg_price = Column(Numeric(18, 9), default=0.0)
    sl = Column(Numeric(18, 9), nullable=True)
    tp = Column(Numeric(18, 9), nullable=True)
    unrealized_pnl = Column(Numeric(18, 9), default=0.0)
    realized_pnl = Column(Numeric(18, 9), default=0.0)
    opened_ts = Column(BigInteger, nullable=False)
    updated_ts = Column(BigInteger, default=now_utc_ms, onupdate=now_utc_ms)


class DecisionLog(Base):
    __tablename__ = "decision_log"

    id = Column(String, primary_key=True)
    ts = Column(BigInteger, nullable=False)
    type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    payload = Column(JSONB, default={})

    __table_args__ = (Index("idx_decision_log_ts", "ts"),)
