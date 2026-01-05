from enum import Enum
from typing import List, Dict, Optional, Any
from decimal import Decimal
from pydantic import BaseModel, Field

class Decision(str, Enum):
    TAKE = "TAKE"
    SKIP = "SKIP"
    REJECT = "REJECT"

class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    BLOCK = "block"

class ReasonCode(str, Enum):
    # Hard Blocks
    RISK_LIMIT_DAILY = "RISK_LIMIT_DAILY"
    RISK_MAX_POSITIONS = "RISK_MAX_POSITIONS"
    RISK_COOLDOWN_ACTIVE = "RISK_COOLDOWN_ACTIVE"
    RISK_MAX_TRADES_DAY = "RISK_MAX_TRADES_DAY"
    INVALID_SIGNAL = "INVALID_SIGNAL"
    NO_MARKET_DATA = "NO_MARKET_DATA"

    # Soft Scores
    REGIME_MATCH = "REGIME_MATCH"
    VOLATILITY_SANITY_OK = "VOLATILITY_SANITY_OK"
    VOLATILITY_SANITY_BAD = "VOLATILITY_SANITY_BAD"
    MOMENTUM_OK = "MOMENTUM_OK"
    MOMENTUM_WEAK = "MOMENTUM_WEAK"
    RSI_OVERHEAT = "RSI_OVERHEAT"
    RSI_OVERSOLD = "RSI_OVERSOLD"
    MACD_CONFLICT = "MACD_CONFLICT"
    LEVEL_CLEARANCE_OK = "LEVEL_CLEARANCE_OK"
    LEVEL_TOO_CLOSE = "LEVEL_TOO_CLOSE"
    LEVEL_UNKNOWN = "LEVEL_UNKNOWN"
    COSTS_OK = "COSTS_OK"
    COSTS_TOO_HIGH = "COSTS_TOO_HIGH"
    RR_TOO_LOW = "RR_TOO_LOW"
    LIQUIDITY_OK = "LIQUIDITY_OK"
    LIQUIDITY_UNKNOWN = "LIQUIDITY_UNKNOWN"
    LIQUIDITY_BAD = "LIQUIDITY_BAD"

class Reason(BaseModel):
    code: ReasonCode
    severity: Severity
    msg: str

class MarketSnapshot(BaseModel):
    # Last N candles for analysis (e.g. 200)
    candles: List[Dict[str, Any]] # [{"close": ..., "time": ...}]
    last_price: Decimal
    spread: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None

class DecisionResult(BaseModel):
    decision: Decision
    # Normalized Percentage (0-100) - Primary for Logic
    score_pct: int 
    threshold_pct: int
    
    # Debug / Calibration Data
    score_raw: int = 0
    score_max: int = 0
    
    # Legacy/Backward compat (optional, can alias to score_pct or score_raw)
    score: int 
    threshold: int 
    
    reasons: List[Reason] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict) # Allow None/Floats
    adjustments: Dict[str, Any] = Field(default_factory=dict)
