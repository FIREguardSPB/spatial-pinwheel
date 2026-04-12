try:
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
except Exception:  # pragma: no cover - lightweight tests without sqlalchemy
    class _DummyType:
        def __init__(self, *args, **kwargs):
            pass

    class _DummyColumn:
        def __init__(self, *args, default=None, **kwargs):
            self.default = default
            self.name = None

        def __set_name__(self, owner, name):
            self.name = name

        def __get__(self, instance, owner):
            if instance is None:
                return self
            return instance.__dict__.get(self.name, None)

        def __set__(self, instance, value):
            instance.__dict__[self.name] = value

    def Column(*args, **kwargs):
        return _DummyColumn(*args, **kwargs)

    Integer = String = Boolean = BigInteger = Text = Numeric = JSONB = _DummyType

    def Index(*args, **kwargs):
        return None

    class Base:
        pass
import datetime


# Helper for UTC (optional use)
def now_utc_ms():
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    risk_profile = Column(String, default="balanced")
    risk_per_trade_pct = Column(Numeric(5, 2), default=0.25)
    daily_loss_limit_pct = Column(Numeric(5, 2), default=1.5)
    max_concurrent_positions = Column(Integer, default=4)
    max_trades_per_day = Column(Integer, default=120)
    rr_target = Column(Numeric(5, 2), default=1.4)
    time_stop_bars = Column(Integer, default=12)
    close_before_session_end_minutes = Column(Integer, default=5)
    cooldown_losses = Column(Integer, default=2)
    cooldown_minutes = Column(Integer, default=30)

    # Decision Engine / Risk
    trade_mode = Column(String, default="review")  # review, auto_paper, auto_live
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
    trading_session = Column(String, default="all")  # main(main+morning) | main+evening/all
    # P5-04: Higher timeframe
    higher_timeframe = Column(String, default="15m")  # HTF for MTF analysis
    # P5-05: Active strategy
    strategy_name = Column(String, default="breakout,mean_reversion")  # breakout | mean_reversion | vwap_bounce
    # P5-06: Correlation
    correlation_threshold = Column(Numeric(4,2), default=0.8)
    max_correlated_positions = Column(Integer, default=2)

    fees_bps = Column(Integer, default=3)  # default 0.03%
    slippage_bps = Column(Integer, default=5)  # default 0.05%
    max_position_notional_pct_balance = Column(Numeric(5, 2), default=10.0)
    max_total_exposure_pct_balance = Column(Numeric(5, 2), default=35.0)
    signal_reentry_cooldown_sec = Column(Integer, default=300)
    pending_review_ttl_sec = Column(Integer, default=900)
    max_pending_per_symbol = Column(Integer, default=1)
    strong_signal_score_threshold = Column(Integer, default=80)
    strong_signal_position_bonus = Column(Integer, default=2)
    partial_close_threshold = Column(Integer, default=80)
    partial_close_ratio = Column(Numeric(5, 2), default=0.50)
    min_position_age_for_partial_close = Column(Integer, default=180)
    worker_bootstrap_limit = Column(Integer, default=10)
    capital_allocator_enabled = Column(Boolean, default=True)
    capital_allocator_min_score_gap = Column(Integer, default=12)
    capital_allocator_min_free_cash_pct = Column(Numeric(5, 2), default=8.0)
    capital_allocator_max_reallocation_pct = Column(Numeric(5, 2), default=0.65)
    capital_allocator_min_edge_improvement = Column(Numeric(6, 3), default=0.18)
    capital_allocator_max_position_concentration_pct = Column(Numeric(5, 2), default=18.0)
    capital_allocator_age_decay_per_hour = Column(Numeric(6, 3), default=0.08)
    portfolio_optimizer_enabled = Column(Boolean, default=True)
    portfolio_optimizer_lookback_bars = Column(Integer, default=180)
    portfolio_optimizer_min_history_bars = Column(Integer, default=60)
    portfolio_optimizer_max_pair_corr = Column(Numeric(5, 2), default=0.85)
    portfolio_optimizer_regime_risk_off_multiplier = Column(Numeric(6, 3), default=0.70)
    portfolio_optimizer_target_weight_buffer_pct = Column(Numeric(5, 2), default=2.50)
    symbol_recalibration_enabled = Column(Boolean, default=True)
    symbol_recalibration_hour_msk = Column(Integer, default=4)
    symbol_recalibration_train_limit = Column(Integer, default=6)
    symbol_recalibration_lookback_days = Column(Integer, default=180)
    event_regime_enabled = Column(Boolean, default=True)
    event_regime_block_severity = Column(Numeric(5, 2), default=0.82)
    adaptive_exit_enabled = Column(Boolean, default=True)
    adaptive_exit_extend_bars_limit = Column(Integer, default=8)
    adaptive_exit_tighten_sl_pct = Column(Numeric(6, 3), default=0.35)
    adaptive_exit_partial_cooldown_sec = Column(Integer, default=180)
    adaptive_exit_max_partial_closes = Column(Integer, default=2)
    signal_freshness_enabled = Column(Boolean, default=True)
    signal_freshness_grace_bars = Column(Numeric(6, 2), default=1.0)
    signal_freshness_penalty_per_bar = Column(Integer, default=6)
    signal_freshness_max_bars = Column(Numeric(6, 2), default=3.0)
    pm_risk_throttle_enabled = Column(Boolean, default=True)
    pm_drawdown_soft_limit_pct = Column(Numeric(5, 2), default=1.5)
    pm_drawdown_hard_limit_pct = Column(Numeric(5, 2), default=3.0)
    pm_loss_streak_soft_limit = Column(Integer, default=2)
    pm_loss_streak_hard_limit = Column(Integer, default=4)
    pm_min_risk_multiplier = Column(Numeric(6, 3), default=0.35)
    auto_degrade_enabled = Column(Boolean, default=True)
    auto_freeze_enabled = Column(Boolean, default=True)
    auto_policy_lookback_days = Column(Integer, default=14)
    auto_degrade_max_execution_errors = Column(Integer, default=4)
    auto_freeze_max_execution_errors = Column(Integer, default=10)
    auto_degrade_min_profit_factor = Column(Numeric(6, 3), default=0.95)
    auto_freeze_min_profit_factor = Column(Numeric(6, 3), default=0.70)
    auto_degrade_min_expectancy = Column(Numeric(18, 4), default=-50.0)
    auto_freeze_min_expectancy = Column(Numeric(18, 4), default=-250.0)
    auto_degrade_drawdown_pct = Column(Numeric(6, 3), default=2.5)
    auto_freeze_drawdown_pct = Column(Numeric(6, 3), default=5.0)
    auto_degrade_risk_multiplier = Column(Numeric(6, 3), default=0.55)
    auto_degrade_threshold_penalty = Column(Integer, default=8)
    auto_freeze_new_entries = Column(Boolean, default=True)
    performance_governor_enabled = Column(Boolean, default=True)
    performance_governor_lookback_days = Column(Integer, default=45)
    performance_governor_min_closed_trades = Column(Integer, default=3)
    performance_governor_strict_whitelist = Column(Boolean, default=True)
    performance_governor_auto_suppress = Column(Boolean, default=True)
    performance_governor_max_execution_error_rate = Column(Numeric(6, 3), default=0.35)
    performance_governor_min_take_fill_rate = Column(Numeric(6, 3), default=0.20)
    performance_governor_pass_risk_multiplier = Column(Numeric(6, 3), default=1.20)
    performance_governor_fail_risk_multiplier = Column(Numeric(6, 3), default=0.60)
    performance_governor_threshold_bonus = Column(Integer, default=6)
    performance_governor_threshold_penalty = Column(Integer, default=10)
    performance_governor_execution_priority_boost = Column(Numeric(6, 3), default=1.20)
    performance_governor_execution_priority_penalty = Column(Numeric(6, 3), default=0.70)
    performance_governor_allocator_boost = Column(Numeric(6, 3), default=1.15)
    performance_governor_allocator_penalty = Column(Numeric(6, 3), default=0.80)
    ml_enabled = Column(Boolean, default=True)
    ml_retrain_enabled = Column(Boolean, default=True)
    ml_lookback_days = Column(Integer, default=120)
    ml_min_training_samples = Column(Integer, default=80)
    ml_retrain_interval_hours = Column(Integer, default=24)
    ml_retrain_hour_msk = Column(Integer, default=4)
    ml_take_probability_threshold = Column(Numeric(6, 3), default=0.55)
    ml_fill_probability_threshold = Column(Numeric(6, 3), default=0.45)
    ml_risk_boost_threshold = Column(Numeric(6, 3), default=0.65)
    ml_risk_cut_threshold = Column(Numeric(6, 3), default=0.45)
    ml_pass_risk_multiplier = Column(Numeric(6, 3), default=1.15)
    ml_fail_risk_multiplier = Column(Numeric(6, 3), default=0.75)
    ml_threshold_bonus = Column(Integer, default=4)
    ml_threshold_penalty = Column(Integer, default=8)
    ml_execution_priority_boost = Column(Numeric(6, 3), default=1.15)
    ml_execution_priority_penalty = Column(Numeric(6, 3), default=0.80)
    ml_allocator_boost = Column(Numeric(6, 3), default=1.10)
    ml_allocator_penalty = Column(Numeric(6, 3), default=0.85)
    ml_allow_take_veto = Column(Boolean, default=True)

    # P6-04: Telegram notifications
    telegram_bot_token   = Column(String, default="")
    telegram_chat_id     = Column(String, default="")
    notification_events  = Column(String, default="signal_created,trade_executed,sl_hit,tp_hit")
    no_notification_hours = Column(String, default="")  # "22,23,0,1,2,3,4,5,6" comma-sep hours

    # P6-11: Account balance (paper mode)
    account_balance = Column(Numeric(18, 4), default=100_000.0)

    # P4-01: AI Advisor settings
    ai_mode = Column(String, default="advisory")          # off | advisory | override | required
    ai_min_confidence = Column(Integer, default=55)  # min AI confidence for OVERRIDE
    ai_primary_provider = Column(String, default="deepseek")
    ai_fallback_providers = Column(String, default="deepseek,ollama,skip")
    ollama_url = Column(String, default="http://localhost:11434")

    # Economic viability guards (FIX26)
    min_sl_distance_pct = Column(Numeric(6, 3), default=0.08)
    min_profit_after_costs_multiplier = Column(Numeric(6, 3), default=1.25)
    min_trade_value_rub = Column(Numeric(18, 4), default=10.0)
    min_instrument_price_rub = Column(Numeric(18, 4), default=0.001)
    min_tick_floor_rub = Column(Numeric(18, 6), default=0.0)
    commission_dominance_warn_ratio = Column(Numeric(6, 3), default=0.30)
    volatility_sl_floor_multiplier = Column(Numeric(6, 3), default=0.0)
    sl_cost_floor_multiplier = Column(Numeric(6, 3), default=0.0)
    use_broker_trading_schedule = Column(Boolean, default=True)
    trading_schedule_exchange = Column(String, default="")
    ai_override_policy = Column(String, default="promote_only")
    is_active = Column(Boolean, default=True)

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
    ai_influenced = Column(Boolean, default=False)
    ai_mode_used = Column(String, default="off")
    ai_decision_id = Column(String, nullable=True)
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
    strategy = Column(String, nullable=True)
    trace_id = Column(String, nullable=True)
    ai_influenced = Column(Boolean, default=False)
    ai_mode_used = Column(String, default="off")
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
    signal_id = Column(String, nullable=True)
    strategy = Column(String, nullable=True)
    trace_id = Column(String, nullable=True)

    __table_args__ = (Index("idx_trades_instrument_ts", "instrument_id", "ts"), Index("idx_trades_trace_id", "trace_id"),)


class Position(Base):
    __tablename__ = "positions"

    instrument_id = Column(String, primary_key=True)
    broker_id = Column(String, nullable=True)  # FIGI / UID
    side = Column(String, nullable=False)
    qty = Column(Numeric(18, 9), default=0.0)
    opened_qty = Column(Numeric(18, 9), default=0.0)
    avg_price = Column(Numeric(18, 9), default=0.0)
    sl = Column(Numeric(18, 9), nullable=True)
    tp = Column(Numeric(18, 9), nullable=True)
    unrealized_pnl = Column(Numeric(18, 9), default=0.0)
    realized_pnl = Column(Numeric(18, 9), default=0.0)
    opened_signal_id = Column(String, nullable=True)
    strategy = Column(String, nullable=True)
    trace_id = Column(String, nullable=True)
    opened_order_id = Column(String, nullable=True)
    closed_order_id = Column(String, nullable=True)
    entry_fee_est = Column(Numeric(18, 9), default=0.0)
    exit_fee_est = Column(Numeric(18, 9), default=0.0)
    total_fees_est = Column(Numeric(18, 9), default=0.0)
    partial_closes_count = Column(Integer, default=0)
    last_partial_close_ts = Column(BigInteger, nullable=True)
    last_mark_price = Column(Numeric(18, 9), nullable=True)
    last_mark_ts = Column(BigInteger, nullable=True)
    mfe_total_pnl = Column(Numeric(18, 9), nullable=True)
    mae_total_pnl = Column(Numeric(18, 9), nullable=True)
    mfe_pct = Column(Numeric(10, 4), nullable=True)
    mae_pct = Column(Numeric(10, 4), nullable=True)
    best_price_seen = Column(Numeric(18, 9), nullable=True)
    worst_price_seen = Column(Numeric(18, 9), nullable=True)
    excursion_samples = Column(Integer, default=0)
    excursion_updated_ts = Column(BigInteger, nullable=True)
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


class SymbolProfile(Base):
    __tablename__ = "symbol_profiles"

    instrument_id = Column(String, primary_key=True)
    enabled = Column(Boolean, default=True)
    preferred_strategies = Column(String, default="breakout,mean_reversion,vwap_bounce")
    decision_threshold_offset = Column(Integer, default=0)
    hold_bars_base = Column(Integer, default=12)
    hold_bars_min = Column(Integer, default=4)
    hold_bars_max = Column(Integer, default=30)
    reentry_cooldown_sec = Column(Integer, default=300)
    risk_multiplier = Column(Numeric(8, 4), default=1.0)
    aggressiveness = Column(Numeric(8, 4), default=1.0)
    autotune = Column(Boolean, default=True)
    session_bias = Column(String, default="all")
    regime_bias = Column(String, default="")
    preferred_side = Column(String, default="both")
    best_hours_json = Column(JSONB, default=[])
    blocked_hours_json = Column(JSONB, default=[])
    news_sensitivity = Column(Numeric(8, 4), default=1.0)
    confidence_bias = Column(Numeric(8, 4), default=1.0)
    notes = Column(Text, nullable=True)
    source = Column(String, default="runtime")
    profile_version = Column(Integer, default=1)
    last_regime = Column(String, nullable=True)
    last_strategy = Column(String, nullable=True)
    last_threshold = Column(Integer, nullable=True)
    last_hold_bars = Column(Integer, nullable=True)
    last_win_rate = Column(Numeric(8, 4), nullable=True)
    sample_size = Column(Integer, default=0)
    last_tuned_ts = Column(BigInteger, default=0)
    created_ts = Column(BigInteger, default=now_utc_ms)
    updated_ts = Column(BigInteger, default=now_utc_ms, onupdate=now_utc_ms)


class SymbolRegimeSnapshot(Base):
    __tablename__ = "symbol_regime_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument_id = Column(String, nullable=False)
    ts = Column(BigInteger, nullable=False)
    timeframe = Column(String, nullable=False, default="1m")
    regime = Column(String, nullable=False, default="balanced")
    volatility_pct = Column(Numeric(12, 6), nullable=True)
    trend_strength = Column(Numeric(12, 6), nullable=True)
    chop_ratio = Column(Numeric(12, 6), nullable=True)
    body_ratio = Column(Numeric(12, 6), nullable=True)
    payload = Column(JSONB, default={})

    __table_args__ = (Index("idx_symbol_regime_snapshots_lookup", "instrument_id", "timeframe", "ts"),)


class SymbolTrainingRun(Base):
    __tablename__ = "symbol_training_runs"

    id = Column(String, primary_key=True)
    ts = Column(BigInteger, nullable=False)
    instrument_id = Column(String, nullable=False)
    mode = Column(String, nullable=False, default="offline")
    status = Column(String, nullable=False, default="completed")
    source = Column(String, nullable=False, default="candle_cache")
    candles_used = Column(Integer, default=0)
    trades_used = Column(Integer, default=0)
    recommendations = Column(JSONB, default={})
    diagnostics = Column(JSONB, default={})
    notes = Column(Text, nullable=True)

    __table_args__ = (Index("idx_symbol_training_runs_lookup", "instrument_id", "ts"),)


class SymbolEventRegime(Base):
    __tablename__ = "symbol_event_regimes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument_id = Column(String, nullable=False)
    ts = Column(BigInteger, nullable=False)
    regime = Column(String, nullable=False, default="calm")
    severity = Column(Numeric(8, 4), nullable=True, default=0.0)
    direction = Column(String, nullable=True)
    score_bias = Column(Integer, nullable=True, default=0)
    hold_bias = Column(Integer, nullable=True, default=0)
    risk_bias = Column(Numeric(8, 4), nullable=True, default=1.0)
    action = Column(String, nullable=True, default="observe")
    payload = Column(JSONB, default={})

    __table_args__ = (Index("idx_symbol_event_regimes_lookup", "instrument_id", "ts"),)


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



class MLTrainingRun(Base):
    __tablename__ = "ml_training_runs"

    id = Column(String, primary_key=True)
    ts = Column(BigInteger, nullable=False)
    target = Column(String, nullable=False)
    status = Column(String, nullable=False, default="completed")
    source = Column(String, nullable=False, default="manual")
    lookback_days = Column(Integer, default=120)
    train_rows = Column(Integer, default=0)
    validation_rows = Column(Integer, default=0)
    artifact_path = Column(Text, nullable=True)
    model_type = Column(String, nullable=False, default="logistic_regression")
    feature_columns = Column(JSONB, default=[])
    metrics = Column(JSONB, default={})
    params = Column(JSONB, default={})
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=False)

    __table_args__ = (
        Index("idx_ml_training_runs_target_ts", "target", "ts"),
        Index("idx_ml_training_runs_active", "target", "is_active", "ts"),
    )


class PositionExcursion(Base):
    __tablename__ = "position_excursions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(String, nullable=True)
    signal_id = Column(String, nullable=True)
    instrument_id = Column(String, nullable=False)
    ts = Column(BigInteger, nullable=False)
    phase = Column(String, nullable=False, default="tick")
    bar_index = Column(Integer, nullable=True)
    mark_price = Column(Numeric(18, 9), nullable=False)
    unrealized_pnl = Column(Numeric(18, 9), nullable=True, default=0.0)
    realized_pnl = Column(Numeric(18, 9), nullable=True, default=0.0)
    lifecycle_pnl = Column(Numeric(18, 9), nullable=True, default=0.0)
    mfe_total_pnl = Column(Numeric(18, 9), nullable=True)
    mae_total_pnl = Column(Numeric(18, 9), nullable=True)
    mfe_pct = Column(Numeric(10, 4), nullable=True)
    mae_pct = Column(Numeric(10, 4), nullable=True)
    is_new_mfe = Column(Boolean, default=False)
    is_new_mae = Column(Boolean, default=False)

    __table_args__ = (
        Index("idx_position_excursions_trace_ts", "trace_id", "ts"),
        Index("idx_position_excursions_instrument_ts", "instrument_id", "ts"),
    )


class CandleCache(Base):
    """Persistent OHLCV cache for faster chart/history bootstrap and backtesting."""
    __tablename__ = "candle_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument_id = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    ts = Column(BigInteger, nullable=False)
    open = Column(Numeric(18, 9), nullable=False)
    high = Column(Numeric(18, 9), nullable=False)
    low = Column(Numeric(18, 9), nullable=False)
    close = Column(Numeric(18, 9), nullable=False)
    volume = Column(BigInteger, default=0)
    source = Column(String, default="worker")
    created_ts = Column(BigInteger, default=now_utc_ms)
    updated_ts = Column(BigInteger, default=now_utc_ms, onupdate=now_utc_ms)

    __table_args__ = (Index("idx_candle_cache_lookup", "instrument_id", "timeframe", "ts", unique=True),)


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

