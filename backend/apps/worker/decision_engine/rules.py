from decimal import Decimal
from typing import Optional
from apps.worker.decision_engine.types import ReasonCode, Severity, Reason

# --- Hard Blocks ---


def check_invalid_signal(
    side: str, entry: Decimal, sl: Decimal, tp: Decimal, size: Decimal
) -> Optional[Reason]:
    if size <= 0:
        return Reason(
            code=ReasonCode.INVALID_SIGNAL, severity=Severity.BLOCK, msg="Size must be > 0"
        )

    if side == "BUY":
        if sl >= entry:
            return Reason(
                code=ReasonCode.INVALID_SIGNAL,
                severity=Severity.BLOCK,
                msg="BUY: SL must be < Entry",
            )
        if tp <= entry:
            return Reason(
                code=ReasonCode.INVALID_SIGNAL,
                severity=Severity.BLOCK,
                msg="BUY: TP must be > Entry",
            )

    elif side == "SELL":
        if sl <= entry:
            return Reason(
                code=ReasonCode.INVALID_SIGNAL,
                severity=Severity.BLOCK,
                msg="SELL: SL must be > Entry",
            )
        if tp >= entry:
            return Reason(
                code=ReasonCode.INVALID_SIGNAL,
                severity=Severity.BLOCK,
                msg="SELL: TP must be < Entry",
            )

    return None


def check_volatility_hard(
    entry: float, sl: float, atr: float, min_dist: float = 0.3, max_dist: float = 5.0
) -> Optional[Reason]:
    """
    Hard Reject: SL too close or too wide relative to ATR
    """
    if atr <= 0:
        return Reason(
            code=ReasonCode.NO_MARKET_DATA, severity=Severity.BLOCK, msg="ATR is zero/negative"
        )

    dist = abs(entry - sl)
    sl_atr = dist / atr

    if sl_atr < min_dist:
        return Reason(
            code=ReasonCode.VOLATILITY_SANITY_BAD,
            severity=Severity.BLOCK,
            msg=f"Stop too tight ({sl_atr:.2f} ATR)",
        )

    if sl_atr > max_dist:
        return Reason(
            code=ReasonCode.VOLATILITY_SANITY_BAD,
            severity=Severity.BLOCK,
            msg=f"Stop too wide ({sl_atr:.2f} ATR)",
        )

    return None


def check_risk_reward(r: float, target: float = 1.5) -> Optional[Reason]:
    """
    Hard Reject: R < Target
    """
    if r < target:
        return Reason(
            code=ReasonCode.RR_TOO_LOW,
            severity=Severity.BLOCK,
            msg=f"R is too low ({r:.2f} < {target})",
        )
    return None


# --- Soft Scores ---


def score_regime(
    close: float, ema50: float, ema50_prev: float, side: str, max_score: int = 20
) -> tuple[int, list[Reason]]:
    """
    Regime Match (0..max_score)
    BUY: Close > EMA50 AND Slope > 0
    """
    score = 0
    reasons = []

    slope = ema50 - ema50_prev

    if side == "BUY":
        if close > ema50 and slope > 0:
            score = max_score
            reasons.append(
                Reason(
                    code=ReasonCode.REGIME_MATCH,
                    severity=Severity.INFO,
                    msg="Uptrend confirmed (Price > EMA, Slope > 0)",
                )
            )
        else:
            reasons.append(
                Reason(
                    code=ReasonCode.REGIME_MATCH,
                    severity=Severity.WARN,
                    msg="Aggressive entry (Counter-trend or Flat)",
                )
            )

    elif side == "SELL":
        if close < ema50 and slope < 0:
            score = max_score
            reasons.append(
                Reason(
                    code=ReasonCode.REGIME_MATCH,
                    severity=Severity.INFO,
                    msg="Downtrend confirmed (Price < EMA, Slope < 0)",
                )
            )
        else:
            reasons.append(
                Reason(
                    code=ReasonCode.REGIME_MATCH,
                    severity=Severity.WARN,
                    msg="Aggressive entry (Counter-trend or Flat)",
                )
            )

    return score, reasons


def score_volatility(
    entry: float,
    sl: float,
    atr: float,
    min_soft: float = 0.6,
    max_soft: float = 2.5,
    max_score: int = 15,
) -> tuple[int, list[Reason]]:
    """
    Volatility Sanity (0..max_score)
    sl_atr = dist / atr
    """
    score = 0
    reasons = []

    dist = abs(entry - sl)
    if atr <= 0:
        return 0, [
            Reason(
                code=ReasonCode.VOLATILITY_SANITY_BAD,
                severity=Severity.WARN,
                msg="ATR is zero/negative",
            )
        ]

    sl_atr = dist / atr

    if min_soft <= sl_atr <= max_soft:
        score = max_score
        reasons.append(
            Reason(
                code=ReasonCode.VOLATILITY_SANITY_OK,
                severity=Severity.INFO,
                msg=f"Stop distance valid ({sl_atr:.2f} ATR)",
            )
        )
    else:
        score = int(max_score / 3)  # Partial
        reasons.append(
            Reason(
                code=ReasonCode.VOLATILITY_SANITY_BAD,
                severity=Severity.WARN,
                msg=f"Stop distance suspicious ({sl_atr:.2f} ATR)",
            )
        )

    return score, reasons


def score_momentum(
    rsi: float, macd_hist: float, side: str, max_score: int = 15
) -> tuple[int, list[Reason]]:
    """
    Momentum (0..max_score)
    Weights: RSI (2/3), MACD (1/3)
    """
    score = 0
    reasons = []

    rsi_weight = int(max_score * 0.67)  # Approx 10/15
    macd_weight = max_score - rsi_weight  # Remainder (approx 5/15)

    # RSI Scoring
    if side == "BUY":
        if 45 <= rsi <= 70:
            score += rsi_weight
            reasons.append(
                Reason(
                    code=ReasonCode.MOMENTUM_OK,
                    severity=Severity.INFO,
                    msg=f"RSI bullish ({rsi:.1f})",
                )
            )
        elif rsi > 70:
            reasons.append(
                Reason(
                    code=ReasonCode.RSI_OVERHEAT,
                    severity=Severity.WARN,
                    msg=f"RSI Overbought ({rsi:.1f})",
                )
            )
        else:
            reasons.append(
                Reason(
                    code=ReasonCode.MOMENTUM_WEAK,
                    severity=Severity.WARN,
                    msg=f"RSI weak ({rsi:.1f})",
                )
            )

        # MACD Scoring
        if macd_hist > 0:
            score += macd_weight
            reasons.append(
                Reason(code=ReasonCode.MOMENTUM_OK, severity=Severity.INFO, msg="MACD Hist > 0")
            )
        else:
            reasons.append(
                Reason(code=ReasonCode.MOMENTUM_WEAK, severity=Severity.WARN, msg="MACD Hist < 0")
            )

    elif side == "SELL":
        if 30 <= rsi <= 55:
            score += rsi_weight
            reasons.append(
                Reason(
                    code=ReasonCode.MOMENTUM_OK,
                    severity=Severity.INFO,
                    msg=f"RSI bearish ({rsi:.1f})",
                )
            )
        elif rsi < 30:
            reasons.append(
                Reason(
                    code=ReasonCode.RSI_OVERSOLD,
                    severity=Severity.WARN,
                    msg=f"RSI Oversold ({rsi:.1f})",
                )
            )
        else:
            reasons.append(
                Reason(
                    code=ReasonCode.MOMENTUM_WEAK,
                    severity=Severity.WARN,
                    msg=f"RSI weak ({rsi:.1f})",
                )
            )

        # MACD Scoring
        if macd_hist < 0:
            score += macd_weight
            reasons.append(
                Reason(code=ReasonCode.MOMENTUM_OK, severity=Severity.INFO, msg="MACD Hist < 0")
            )
        else:
            reasons.append(
                Reason(code=ReasonCode.MOMENTUM_WEAK, severity=Severity.WARN, msg="MACD Hist > 0")
            )

    return score, reasons


def score_levels(
    entry: float, tp: float, nearest_level: Optional[float], side: str, max_score: int = 20
) -> tuple[int, list[Reason]]:
    """
    Level Clearance (0..max_score).
    If nearest_level is None (not found) -> Neutral score (max/2) + LEVEL_UNKNOWN (P0 Fix)
    Ratio = dist_to_level / tp_distance
    >= 0.7 OK
    Note: 'side' param reserved for future asymmetry logic (e.g. Support vs Resistance bias).
    """
    if nearest_level is None:
        return int(max_score / 2), [
            Reason(
                code=ReasonCode.LEVEL_UNKNOWN,
                severity=Severity.INFO,
                msg="No level found in window",
            )
        ]

    score = 0
    reasons = []

    tp_dist = abs(entry - tp)
    level_dist = abs(entry - nearest_level)

    # Logic: If level is closer than TP, we might hit it first.
    # We simplified in v1 spec: clearance_ratio = dist_to_level / tp_distance
    if tp_dist == 0:
        return 0, []

    ratio = level_dist / tp_dist

    # P0.6 Normalization: Clamp ratio to 1.0 max to strictly respect max_score
    ratio = max(0.0, min(ratio, 1.0))

    # Formula A: Strict Linear Scoring
    # Ratio 1.0 -> 100% score. Ratio 0.5 -> 50% score.
    score = int(max_score * ratio)

    if ratio >= 0.7:
        reasons.append(
            Reason(
                code=ReasonCode.LEVEL_CLEARANCE_OK,
                severity=Severity.INFO,
                msg=f"Room to move (Ratio {ratio:.2f})",
            )
        )
    else:
        reasons.append(
            Reason(
                code=ReasonCode.LEVEL_TOO_CLOSE,
                severity=Severity.WARN,
                msg=f"Level too close (Ratio {ratio:.2f})",
            )
        )

    return score, reasons


def score_costs(
    entry: float, sl: float, tp: float, fees_bps: int, slippage_bps: int, max_score: int = 15
) -> tuple[int, list[Reason]]:
    """
    Costs (0..max_score)
    RR after costs >= 1.5 (or target) -> max_score
    """
    score = 0
    reasons = []

    # Convert bps to multiplier
    fee_pct = fees_bps / 10000.0
    slip_pct = slippage_bps / 10000.0
    total_cost_pct = fee_pct + slip_pct

    # Cost in price terms (approx)
    cost_price = entry * total_cost_pct

    raw_profit = abs(tp - entry)
    raw_loss = abs(entry - sl)

    net_profit = raw_profit - (cost_price * 2)  # Entry + Exit
    net_loss = raw_loss + (cost_price * 2)

    if net_loss <= 0:
        return 0, [
            Reason(code=ReasonCode.COSTS_TOO_HIGH, severity=Severity.BLOCK, msg="Costs exceed risk")
        ]

    rr = net_profit / net_loss

    if rr >= 1.5:  # Using hardcoded 1.5 as min acceptable for full score in v1, or pass targets
        score = max_score
        reasons.append(
            Reason(code=ReasonCode.COSTS_OK, severity=Severity.INFO, msg=f"Net RR {rr:.2f} OK")
        )
    elif rr > 1.0:
        score = int(max_score / 3)
        reasons.append(
            Reason(
                code=ReasonCode.COSTS_TOO_HIGH, severity=Severity.WARN, msg=f"Net RR {rr:.2f} Low"
            )
        )
    else:
        score = 0
        reasons.append(
            Reason(
                code=ReasonCode.COSTS_TOO_HIGH,
                severity=Severity.WARN,
                msg=f"Net RR {rr:.2f} Negative Exp",
            )
        )

    return score, reasons
