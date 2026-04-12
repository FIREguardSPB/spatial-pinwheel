from pydantic import BaseModel, ConfigDict, PlainSerializer
from typing import Optional, Any, Dict, List, Literal, Annotated
from decimal import Decimal

# Custom type: Decimal logic internally, Float serialization externally (for JSON/Frontend)
DecimalFloat = Annotated[Decimal, PlainSerializer(lambda x: float(x), return_type=float)]


# --- Settings ---
class RiskSettings(BaseModel):
    id: Optional[int] = None
    updated_ts: Optional[int] = None
    is_active: Optional[bool] = None
    risk_profile: str
    risk_per_trade_pct: DecimalFloat
    daily_loss_limit_pct: DecimalFloat
    max_concurrent_positions: int
    max_trades_per_day: int
    fees_bps: Optional[int] = 3
    slippage_bps: Optional[int] = 5
    max_position_notional_pct_balance: Optional[DecimalFloat] = 10.0
    max_total_exposure_pct_balance: Optional[DecimalFloat] = 35.0
    signal_reentry_cooldown_sec: Optional[int] = 300
    pending_review_ttl_sec: Optional[int] = 900
    max_pending_per_symbol: Optional[int] = 1
    strong_signal_score_threshold: Optional[int] = 80
    strong_signal_position_bonus: Optional[int] = 2
    partial_close_threshold: Optional[int] = 80
    partial_close_ratio: Optional[DecimalFloat] = 0.5
    min_position_age_for_partial_close: Optional[int] = 180
    worker_bootstrap_limit: Optional[int] = 10
    capital_allocator_enabled: Optional[bool] = True
    capital_allocator_min_score_gap: Optional[int] = 12
    capital_allocator_min_free_cash_pct: Optional[DecimalFloat] = 8.0
    capital_allocator_max_reallocation_pct: Optional[DecimalFloat] = 0.65
    capital_allocator_min_edge_improvement: Optional[DecimalFloat] = 0.18
    capital_allocator_max_position_concentration_pct: Optional[DecimalFloat] = 18.0
    capital_allocator_age_decay_per_hour: Optional[DecimalFloat] = 0.08
    portfolio_optimizer_enabled: Optional[bool] = True
    portfolio_optimizer_lookback_bars: Optional[int] = 180
    portfolio_optimizer_min_history_bars: Optional[int] = 60
    portfolio_optimizer_max_pair_corr: Optional[DecimalFloat] = 0.85
    portfolio_optimizer_regime_risk_off_multiplier: Optional[DecimalFloat] = 0.70
    portfolio_optimizer_target_weight_buffer_pct: Optional[DecimalFloat] = 2.5
    symbol_recalibration_enabled: Optional[bool] = True
    symbol_recalibration_hour_msk: Optional[int] = 4
    symbol_recalibration_train_limit: Optional[int] = 6
    symbol_recalibration_lookback_days: Optional[int] = 180
    event_regime_enabled: Optional[bool] = True
    event_regime_block_severity: Optional[DecimalFloat] = 0.82
    adaptive_exit_enabled: Optional[bool] = True
    adaptive_exit_extend_bars_limit: Optional[int] = 8
    adaptive_exit_tighten_sl_pct: Optional[DecimalFloat] = 0.35
    adaptive_exit_partial_cooldown_sec: Optional[int] = 180
    adaptive_exit_max_partial_closes: Optional[int] = 2
    signal_freshness_enabled: Optional[bool] = True
    signal_freshness_grace_bars: Optional[DecimalFloat] = 1.0
    signal_freshness_penalty_per_bar: Optional[int] = 6
    signal_freshness_max_bars: Optional[DecimalFloat] = 3.0
    pm_risk_throttle_enabled: Optional[bool] = True
    pm_drawdown_soft_limit_pct: Optional[DecimalFloat] = 1.5
    pm_drawdown_hard_limit_pct: Optional[DecimalFloat] = 3.0
    pm_loss_streak_soft_limit: Optional[int] = 2
    pm_loss_streak_hard_limit: Optional[int] = 4
    pm_min_risk_multiplier: Optional[DecimalFloat] = 0.35
    auto_degrade_enabled: Optional[bool] = True
    auto_freeze_enabled: Optional[bool] = True
    auto_policy_lookback_days: Optional[int] = 14
    auto_degrade_max_execution_errors: Optional[int] = 4
    auto_freeze_max_execution_errors: Optional[int] = 10
    auto_degrade_min_profit_factor: Optional[DecimalFloat] = 0.95
    auto_freeze_min_profit_factor: Optional[DecimalFloat] = 0.70
    auto_degrade_min_expectancy: Optional[DecimalFloat] = -50.0
    auto_freeze_min_expectancy: Optional[DecimalFloat] = -250.0
    auto_degrade_drawdown_pct: Optional[DecimalFloat] = 2.5
    auto_freeze_drawdown_pct: Optional[DecimalFloat] = 5.0
    auto_degrade_risk_multiplier: Optional[DecimalFloat] = 0.55
    auto_degrade_threshold_penalty: Optional[int] = 8
    auto_freeze_new_entries: Optional[bool] = True
    performance_governor_enabled: Optional[bool] = True
    performance_governor_lookback_days: Optional[int] = 45
    performance_governor_min_closed_trades: Optional[int] = 3
    performance_governor_strict_whitelist: Optional[bool] = True
    performance_governor_auto_suppress: Optional[bool] = True
    performance_governor_max_execution_error_rate: Optional[DecimalFloat] = 0.35
    performance_governor_min_take_fill_rate: Optional[DecimalFloat] = 0.20
    performance_governor_pass_risk_multiplier: Optional[DecimalFloat] = 1.20
    performance_governor_fail_risk_multiplier: Optional[DecimalFloat] = 0.60
    performance_governor_threshold_bonus: Optional[int] = 6
    performance_governor_threshold_penalty: Optional[int] = 10
    performance_governor_execution_priority_boost: Optional[DecimalFloat] = 1.20
    performance_governor_execution_priority_penalty: Optional[DecimalFloat] = 0.70
    performance_governor_allocator_boost: Optional[DecimalFloat] = 1.15
    performance_governor_allocator_penalty: Optional[DecimalFloat] = 0.80
    ml_enabled: Optional[bool] = True
    ml_retrain_enabled: Optional[bool] = True
    ml_lookback_days: Optional[int] = 120
    ml_min_training_samples: Optional[int] = 80
    ml_retrain_interval_hours: Optional[int] = 24
    ml_retrain_hour_msk: Optional[int] = 4
    ml_take_probability_threshold: Optional[DecimalFloat] = 0.55
    ml_fill_probability_threshold: Optional[DecimalFloat] = 0.45
    ml_risk_boost_threshold: Optional[DecimalFloat] = 0.65
    ml_risk_cut_threshold: Optional[DecimalFloat] = 0.45
    ml_pass_risk_multiplier: Optional[DecimalFloat] = 1.15
    ml_fail_risk_multiplier: Optional[DecimalFloat] = 0.75
    ml_threshold_bonus: Optional[int] = 4
    ml_threshold_penalty: Optional[int] = 8
    ml_execution_priority_boost: Optional[DecimalFloat] = 1.15
    ml_execution_priority_penalty: Optional[DecimalFloat] = 0.80
    ml_allocator_boost: Optional[DecimalFloat] = 1.10
    ml_allocator_penalty: Optional[DecimalFloat] = 0.85
    ml_allow_take_veto: Optional[bool] = True
    rr_target: DecimalFloat
    time_stop_bars: int
    close_before_session_end_minutes: int
    cooldown_after_losses: Dict[str, int] = {"losses": 2, "minutes": 60}

    # Strictness / Decision Engine
    atr_stop_hard_min: Optional[DecimalFloat] = 0.6
    atr_stop_hard_max: Optional[DecimalFloat] = 2.5
    atr_stop_soft_min: Optional[DecimalFloat] = 0.8
    atr_stop_soft_max: Optional[DecimalFloat] = 2.5
    rr_min: Optional[DecimalFloat] = 1.5
    decision_threshold: Optional[int] = 70
    w_regime: Optional[int] = 20
    w_volatility: Optional[int] = 15
    w_momentum: Optional[int] = 15
    w_levels: Optional[int] = 20
    w_costs: Optional[int] = 15
    w_liquidity: Optional[int] = 5
    w_volume: Optional[int] = 10

    # Strategy (P5-05)
    strategy_name: Optional[str] = "breakout"

    # AI settings (P4)
    ai_mode: Optional[str] = "advisory"
    ai_min_confidence: Optional[int] = 55
    ai_primary_provider: Optional[str] = "deepseek"
    ai_fallback_providers: Optional[str] = "deepseek,ollama,skip"
    ollama_url: Optional[str] = "http://localhost:11434"

    # Economic viability guards (FIX26)
    min_sl_distance_pct: Optional[DecimalFloat] = 0.08
    min_profit_after_costs_multiplier: Optional[DecimalFloat] = 1.25
    min_trade_value_rub: Optional[DecimalFloat] = 10.0
    min_instrument_price_rub: Optional[DecimalFloat] = 0.001
    min_tick_floor_rub: Optional[DecimalFloat] = 0.0
    commission_dominance_warn_ratio: Optional[DecimalFloat] = 0.30
    volatility_sl_floor_multiplier: Optional[DecimalFloat] = 0.0
    sl_cost_floor_multiplier: Optional[DecimalFloat] = 0.0

    # Session (P5-03)
    no_trade_opening_minutes: Optional[int] = 10
    higher_timeframe: Optional[str] = "15m"
    trading_session: Optional[str] = "all"
    use_broker_trading_schedule: Optional[bool] = True
    trading_schedule_exchange: Optional[str] = ""

    # AI merge policy
    ai_override_policy: Optional[str] = "promote_only"

    # Correlation (P5-06)
    correlation_threshold: Optional[float] = 0.8
    max_correlated_positions: Optional[int] = 2

    # Telegram (P6-04)
    telegram_bot_token: Optional[str] = ""
    telegram_chat_id: Optional[str] = ""
    notification_events: Optional[str] = "signal_created,trade_executed,sl_hit,tp_hit"

    # Account
    account_balance: Optional[float] = 100_000.0
    trade_mode: Optional[str] = "review"
    bot_enabled: Optional[bool] = False


# --- Signals ---
class Signal(BaseModel):
    id: str
    instrument_id: str
    ts: int
    created_ts: Optional[int] = None
    updated_ts: Optional[int] = None
    side: Literal["BUY", "SELL"]
    entry: DecimalFloat
    sl: DecimalFloat
    tp: DecimalFloat
    size: DecimalFloat
    r: DecimalFloat
    status: Literal["pending_review", "approved", "rejected", "executed", "expired", "execution_error", "skipped"]
    final_decision: Optional[Literal["TAKE", "SKIP", "REJECT"]] = None
    economic_summary: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    meta: Dict[str, Any] = {}  # decision, score, reasons
    strategy_name: Optional[str] = None
    strategy_source: Optional[str] = None
    ai_influence: Optional[str] = None
    reject_reason_priority: Optional[str] = None
    geometry_optimized: Optional[bool] = None
    geometry_phase: Optional[str] = None
    geometry_action: Optional[str] = None
    geometry_source: Optional[str] = None
    analysis_timeframe: Optional[str] = None
    execution_timeframe: Optional[str] = None
    confirmation_timeframe: Optional[str] = None
    timeframe_selection_reason: Optional[str] = None
    ai_influenced: bool = False
    ai_mode_used: Optional[str] = None
    ai_decision_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SignalList(BaseModel):
    items: List[Signal]
    next_cursor: Optional[str] = None


class ApproveSignal(BaseModel):
    comment: Optional[str] = None
    override: Optional[Dict[str, Any]] = None


class RejectSignal(BaseModel):
    comment: Optional[str] = None


# --- Orders ---
class Order(BaseModel):
    order_id: str
    instrument_id: str
    ts: int
    side: Literal["BUY", "SELL"]
    type: Literal["LIMIT", "MARKET", "STOP"]
    price: Optional[DecimalFloat]
    qty: DecimalFloat
    filled_qty: DecimalFloat
    status: str
    related_signal_id: Optional[str] = None
    ai_influenced: bool = False
    ai_mode_used: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ErrorInfo(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None
    error_id: Optional[str] = None


class OrderList(BaseModel):
    items: List[Order]
    degraded: bool = False
    error: Optional[ErrorInfo] = None


# --- Positions ---
class Position(BaseModel):
    instrument_id: str
    side: Literal["BUY", "SELL"]
    qty: DecimalFloat
    opened_qty: Optional[DecimalFloat] = None
    avg_price: DecimalFloat
    unrealized_pnl: DecimalFloat
    realized_pnl: DecimalFloat
    sl: Optional[DecimalFloat]
    tp: Optional[DecimalFloat]
    opened_signal_id: Optional[str] = None
    opened_order_id: Optional[str] = None
    closed_order_id: Optional[str] = None
    entry_fee_est: Optional[DecimalFloat] = None
    exit_fee_est: Optional[DecimalFloat] = None
    total_fees_est: Optional[DecimalFloat] = None
    partial_closes_count: Optional[int] = None
    last_partial_close_ts: Optional[int] = None
    last_mark_price: Optional[DecimalFloat] = None
    last_mark_ts: Optional[int] = None
    mfe_total_pnl: Optional[DecimalFloat] = None
    mae_total_pnl: Optional[DecimalFloat] = None
    mfe_pct: Optional[DecimalFloat] = None
    mae_pct: Optional[DecimalFloat] = None
    best_price_seen: Optional[DecimalFloat] = None
    worst_price_seen: Optional[DecimalFloat] = None
    excursion_samples: Optional[int] = None
    excursion_updated_ts: Optional[int] = None
    opened_ts: int
    updated_ts: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PositionList(BaseModel):
    items: List[Position]
    degraded: bool = False
    error: Optional[ErrorInfo] = None


# --- Trades ---
class Trade(BaseModel):
    trade_id: str
    signal_id: Optional[str] = None
    instrument_id: str
    ts: int
    side: Literal["BUY", "SELL"]
    price: DecimalFloat
    qty: DecimalFloat
    order_id: str
    strategy: Optional[str] = None
    trace_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TradeList(BaseModel):
    items: List[Trade]
    degraded: bool = False
    error: Optional[ErrorInfo] = None


# --- Decision Log ---
class LogEntry(BaseModel):
    id: str
    ts: int
    type: str
    message: str
    payload: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class LogList(BaseModel):
    items: List[LogEntry]
    next_cursor: Optional[str] = None


# --- Market Data ---
class Candle(BaseModel):
    time: int
    open: DecimalFloat
    high: DecimalFloat
    low: DecimalFloat
    close: DecimalFloat
    volume: int
    is_complete: bool = True


class CandleList(BaseModel):
    items: List[Candle]


class ManualMarketOrderRequest(BaseModel):
    instrument_id: str
    side: Literal["BUY", "SELL"]
    qty: DecimalFloat
    qty_mode: Literal["lots", "units"] = "lots"
    reference_price: Optional[DecimalFloat] = None
    comment: Optional[str] = None


class ManualLimitOrderRequest(ManualMarketOrderRequest):
    price: DecimalFloat


class ManualOrderResponse(BaseModel):
    status: str
    order_id: str
    broker_order_id: Optional[str] = None
    filled_price: Optional[DecimalFloat] = None
    detail: Optional[str] = None
