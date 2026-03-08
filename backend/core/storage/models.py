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
    trade_mode = Column(String, default="review")  # review | auto_paper | auto_live
    bot_enabled = Column(Boolean, default=False)
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
    # P5-02: Volume weight
    w_volume = Column(Integer, default=10)
    # P5-03: Session settings
    no_trade_opening_minutes = Column(Integer, default=10)
    trading_session = Column(String, default="main")  # main | main+evening | all
    # P5-04: Higher timeframe
    higher_timeframe = Column(String, default="15m")  # HTF for MTF analysis
    # P5-05: Active strategy
    strategy_name = Column(String, default="breakout")  # breakout | mean_reversion | vwap_bounce
    # P5-06: Correlation
    correlation_threshold = Column(Numeric(4,2), default=0.8)
    max_correlated_positions = Column(Integer, default=2)

    fees_bps = Column(Integer, default=3)  # default 0.03%
    slippage_bps = Column(Integer, default=5)  # default 0.05%

    # P6-04: Telegram notifications
    telegram_bot_token   = Column(String, default="")
    telegram_chat_id     = Column(String, default="")
    notification_events  = Column(String, default="signal_created,trade_executed,sl_hit,tp_hit")
    no_notification_hours = Column(String, default="")  # "22,23,0,1,2,3,4,5,6" comma-sep hours

    # P6-11: Account balance (paper mode)
    account_balance = Column(Numeric(18, 4), default=100_000.0)

    # P4-01: AI Advisor settings
    ai_mode = Column(String, default="off")          # off | advisory | override | required
    ai_min_confidence = Column(Integer, default=70)  # min AI confidence for OVERRIDE
    ai_primary_provider = Column(String, default="claude")
    ai_fallback_providers = Column(String, default="ollama,skip")
    ollama_url = Column(String, default="http://localhost:11434")

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


class AccountSnapshot(Base):
    """
    P2-08: Снимки equity curve для бумажной торговли.
    Записываются воркером раз в N минут / на каждое закрытие позиции.
    Используются для графика equity curve в P6-11.
    """
    __tablename__ = "account_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(BigInteger, nullable=False)           # Unix ms
    balance = Column(Numeric(18, 4), default=0.0)     # Денежные средства
    equity = Column(Numeric(18, 4), default=0.0)      # balance + unrealized_pnl
    open_positions = Column(Integer, default=0)       # Количество открытых позиций
    day_pnl = Column(Numeric(18, 4), default=0.0)     # PnL за день

    __table_args__ = (Index("idx_snapshots_ts", "ts"),)


class AIDecisionLog(Base):
    """
    P4-07: Каждое AI-решение записывается для аудита и датасета fine-tuning.
    actual_outcome обновляется PositionMonitor после закрытия позиции.
    """
    __tablename__ = "ai_decisions"

    id = Column(String, primary_key=True)
    ts = Column(BigInteger, nullable=False)
    signal_id = Column(String, nullable=False)
    instrument_id = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    prompt_hash = Column(String(64), nullable=True)
    response_raw = Column(Text, nullable=True)
    ai_decision = Column(String, nullable=False)
    ai_confidence = Column(Integer, default=0)
    ai_reasoning = Column(Text, nullable=True)
    ai_key_factors = Column(JSONB, default=[])
    final_decision = Column(String, nullable=False)
    de_score = Column(Integer, default=0)
    actual_outcome = Column(String, default="pending")
    latency_ms = Column(Integer, default=0)

    __table_args__ = (Index("idx_ai_decisions_ts", "ts"),)


class Watchlist(Base):
    """P6-09: Dynamic instrument watchlist (replaces hardcoded tickers in worker)."""
    __tablename__ = "watchlist"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    instrument_id = Column(String, unique=True, nullable=False)   # "TQBR:SBER"
    ticker        = Column(String, nullable=False)                 # "SBER"
    name          = Column(String, nullable=False)                 # "Сбербанк"
    exchange      = Column(String, default="TQBR")
    is_active     = Column(Boolean, default=True)
    added_ts      = Column(BigInteger, nullable=False)

    __table_args__ = (Index("idx_watchlist_instrument_id", "instrument_id"),)

class ApiToken(Base):
    """
    P8-01: API-токены, управляемые через UI.

    Хранит все секреты приложения: AUTH_TOKEN, Telegram, Claude, OpenAI, T-Bank и т.д.
    При старте воркера/API приоритет: Settings > ApiToken > env-переменная.

    Значение хранится в открытом виде (шифрование — опционально через Fernet в P8-02).
    Маскирование происходит на уровне API (last 4 символа).
    """
    __tablename__ = "api_tokens"

    id          = Column(String, primary_key=True)          # e.g. "tok_uuid"
    key_name    = Column(String, nullable=False, unique=True) # "CLAUDE_API_KEY", "TELEGRAM_BOT_TOKEN"
    value       = Column(String, nullable=False, default="")  # actual secret
    label       = Column(String, default="")                  # human name: "Claude API Key"
    description = Column(String, default="")                  # what it's used for
    category    = Column(String, default="general")           # ai | telegram | broker | auth
    is_active   = Column(Boolean, default=True)
    created_ts  = Column(BigInteger, default=now_utc_ms)
    updated_ts  = Column(BigInteger, default=now_utc_ms, onupdate=now_utc_ms)
    last_used_ts = Column(BigInteger, nullable=True)

    __table_args__ = (Index("idx_api_tokens_key_name", "key_name"),)

