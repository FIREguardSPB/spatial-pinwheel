from pydantic import BaseModel, ConfigDict, PlainSerializer
from typing import Optional, Any, Dict, List, Literal, Annotated
from decimal import Decimal

# Custom type: Decimal logic internally, Float serialization externally (for JSON/Frontend)
DecimalFloat = Annotated[Decimal, PlainSerializer(lambda x: float(x), return_type=float)]


# --- Settings ---
class RiskSettings(BaseModel):
    risk_profile: str
    risk_per_trade_pct: DecimalFloat
    daily_loss_limit_pct: DecimalFloat
    max_concurrent_positions: int
    max_trades_per_day: int
    rr_target: DecimalFloat
    time_stop_bars: int
    close_before_session_end_minutes: int
    cooldown_after_losses: Dict[str, int] = {"losses": 2, "minutes": 60}

    # Strictness / Decision Engine
    atr_stop_hard_min: Optional[DecimalFloat] = 0.6
    atr_stop_hard_max: Optional[DecimalFloat] = 2.5
    atr_stop_soft_min: Optional[DecimalFloat] = 0.8
    atr_stop_soft_max: Optional[DecimalFloat] = 2.0
    rr_min: Optional[DecimalFloat] = 1.5
    decision_threshold: Optional[int] = 70
    w_regime: Optional[int] = 20
    w_volatility: Optional[int] = 15
    w_momentum: Optional[int] = 15
    w_levels: Optional[int] = 20
    w_costs: Optional[int] = 15
    w_liquidity: Optional[int] = 5


# --- Signals ---
class Signal(BaseModel):
    id: str
    instrument_id: str
    ts: int
    side: Literal["BUY", "SELL"]
    entry: DecimalFloat
    sl: DecimalFloat
    tp: DecimalFloat
    size: DecimalFloat
    r: DecimalFloat
    status: Literal["pending_review", "approved", "rejected", "executed", "expired"]
    reason: Optional[str] = None
    meta: Dict[str, Any] = {}  # decision, score, reasons

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

    model_config = ConfigDict(from_attributes=True)


class OrderList(BaseModel):
    items: List[Order]


# --- Positions ---
class Position(BaseModel):
    instrument_id: str
    side: Literal["BUY", "SELL"]
    qty: DecimalFloat
    avg_price: DecimalFloat
    unrealized_pnl: DecimalFloat
    realized_pnl: DecimalFloat
    sl: Optional[DecimalFloat]
    tp: Optional[DecimalFloat]
    opened_ts: int

    model_config = ConfigDict(from_attributes=True)


class PositionList(BaseModel):
    items: List[Position]


# --- Trades ---
class Trade(BaseModel):
    trade_id: str
    instrument_id: str
    ts: int
    side: Literal["BUY", "SELL"]
    price: DecimalFloat
    qty: DecimalFloat
    order_id: str

    model_config = ConfigDict(from_attributes=True)


class TradeList(BaseModel):
    items: List[Trade]


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
