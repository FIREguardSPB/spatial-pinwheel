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
                msg=f"Stop distance suspicious ({sl_atr:.2f} ATR; expected {min_soft:.2f}-{max_soft:.2f})",
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
    Level clearance score (0..max_score).

    The ratio here is **not** the ATR stop ratio. It is the share of the TP path
    available before the nearest opposing level is reached.
    """
    if nearest_level is None:
        return int(max_score / 2), [
            Reason(
                code=ReasonCode.LEVEL_UNKNOWN,
                severity=Severity.INFO,
                msg="No opposing level found in lookback window",
            )
        ]

    tp_dist = abs(entry - tp)
    if tp_dist <= 1e-9:
        return 0, [
            Reason(
                code=ReasonCode.LEVEL_UNKNOWN,
                severity=Severity.WARN,
                msg="TP distance is zero — cannot score level clearance",
            )
        ]

    level_dist = abs(entry - nearest_level)
    ratio_raw = level_dist / tp_dist
    ratio_clamped = max(0.0, min(ratio_raw, 1.0))
    ratio_display = max(round(ratio_raw, 2), 0.01) if ratio_raw > 0 else 0.0
    score = int(max_score * ratio_clamped)

    level_name = 'resistance' if side == 'BUY' else 'support'
    if ratio_clamped >= 0.7:
        return score, [
            Reason(
                code=ReasonCode.LEVEL_CLEARANCE_OK,
                severity=Severity.INFO,
                msg=f"Nearest {level_name} leaves room ({ratio_display:.2f} of TP path)",
            )
        ]

    return score, [
        Reason(
            code=ReasonCode.LEVEL_TOO_CLOSE,
            severity=Severity.WARN,
            msg=f"Nearest {level_name} too close ({ratio_display:.2f} of TP path)",
        )
    ]


def analyze_costs(entry: float, sl: float, tp: float, fees_bps: int, slippage_bps: int) -> dict:
    """Return cost / RR breakdown used both for scoring and diagnostics."""
    fee_pct = fees_bps / 10000.0
    slip_pct = slippage_bps / 10000.0
    total_cost_pct = fee_pct + slip_pct

    raw_profit = abs(tp - entry)
    raw_loss = abs(entry - sl)
    round_trip_cost = entry * total_cost_pct * 2.0
    net_profit = raw_profit - round_trip_cost
    net_loss = raw_loss + round_trip_cost

    gross_rr = (raw_profit / raw_loss) if raw_loss > 0 else None
    net_rr = (net_profit / net_loss) if net_loss > 0 else None

    return {
        "fee_pct": fee_pct,
        "slip_pct": slip_pct,
        "cost_pct_total": total_cost_pct,
        "round_trip_cost": round_trip_cost,
        "raw_profit": raw_profit,
        "raw_loss": raw_loss,
        "net_profit": net_profit,
        "net_loss": net_loss,
        "gross_rr": gross_rr,
        "net_rr": net_rr,
    }


def score_costs(
    entry: float, sl: float, tp: float, fees_bps: int, slippage_bps: int, max_score: int = 15
) -> tuple[int, list[Reason], dict]:
    """
    Costs (0..max_score)
    RR after costs >= 1.5 -> max_score.
    Returns (score, reasons, breakdown).
    """
    score = 0
    reasons = []
    breakdown = analyze_costs(entry, sl, tp, fees_bps, slippage_bps)

    net_rr = breakdown["net_rr"]
    net_profit = breakdown["net_profit"]
    net_loss = breakdown["net_loss"]

    if net_loss is None or net_loss <= 0:
        return 0, [
            Reason(code=ReasonCode.COSTS_TOO_HIGH, severity=Severity.BLOCK, msg="Costs exceed risk")
        ], breakdown

    if net_rr is None:
        return 0, [
            Reason(code=ReasonCode.COSTS_TOO_HIGH, severity=Severity.WARN, msg="Net RR unavailable")
        ], breakdown

    if net_profit <= 0 or net_rr <= 0:
        reasons.append(
            Reason(
                code=ReasonCode.COSTS_TOO_HIGH,
                severity=Severity.WARN,
                msg=f"Net RR {net_rr:.2f} Non-positive after costs",
            )
        )
        return 0, reasons, breakdown

    if net_rr >= 1.5:
        score = max_score
        reasons.append(
            Reason(code=ReasonCode.COSTS_OK, severity=Severity.INFO, msg=f"Net RR {net_rr:.2f} OK")
        )
    elif net_rr >= 1.0:
        score = int(max_score / 3)
        reasons.append(
            Reason(
                code=ReasonCode.COSTS_TOO_HIGH,
                severity=Severity.WARN,
                msg=f"Net RR {net_rr:.2f} Below target after costs",
            )
        )
    else:
        score = 0
        reasons.append(
            Reason(
                code=ReasonCode.COSTS_TOO_HIGH,
                severity=Severity.WARN,
                msg=f"Net RR {net_rr:.2f} Sub-1 after costs",
            )
        )

    return score, reasons, breakdown


# ─── P5-02: Volume Filter ─────────────────────────────────────────────────────

def score_volume(
    volume_ratio: float,
    max_score: int = 10,
    min_ratio: float = 0.5,
    anomalous_ratio: float = 8.0,
    extreme_ratio: float = 20.0,
) -> tuple[int, "Reason"]:
    """
    Volume-based score.
    Returns (score, reason).

    < min_ratio       → BLOCK (dead market)
    > extreme_ratio   → WARN  (extreme spike)
    > anomalous_ratio → WARN  (anomalous spike)
    else              → OK
    """
    if volume_ratio is None:
        half = max_score // 2
        return half, Reason(
            code=ReasonCode.VOLUME_OK,
            severity=Severity.INFO,
            msg="Volume ratio unavailable — partial score",
        )
    if volume_ratio < min_ratio:
        return 0, Reason(
            code=ReasonCode.VOLUME_LOW,
            severity=Severity.BLOCK,
            msg=f"Volume too low ({volume_ratio:.2f}x avg) — min {min_ratio:.1f}x",
        )
    if volume_ratio > extreme_ratio:
        half = max_score // 2
        return half, Reason(
            code=ReasonCode.VOLUME_ANOMALOUS,
            severity=Severity.WARN,
            msg=f"Extreme volume spike ({volume_ratio:.2f}x avg; warn ≥ {extreme_ratio:.1f}x)",
        )
    if volume_ratio > anomalous_ratio:
        half = max_score // 2
        return half, Reason(
            code=ReasonCode.VOLUME_ANOMALOUS,
            severity=Severity.WARN,
            msg=f"Volume spike ({volume_ratio:.2f}x avg; warn ≥ {anomalous_ratio:.1f}x)",
        )
    return max_score, Reason(
        code=ReasonCode.VOLUME_OK,
        severity=Severity.INFO,
        msg=f"Volume OK ({volume_ratio:.2f}x avg)",
    )


# ─── P5-03: Session Filter ───────────────────────────────────────────────────

def check_session(
    no_trade_opening_minutes: int = 10,
    close_before_end_minutes: int = 10,
    session_type: str = "all",
) -> "Optional[Reason]":
    """
    P5-03: Hard-reject if outside trading session or too close to open/close.
    Returns Reason (BLOCK) if trading not allowed, None if OK.
    """
    from core.utils.session import (
        is_trading_session, minutes_until_session_end,
        _msk_now, current_session_bounds,
    )

    if not is_trading_session(session_type):
        return Reason(
            code=ReasonCode.SESSION_CLOSED,
            severity=Severity.BLOCK,
            msg="Outside MOEX trading session",
        )

    # Opening gap protection: first N minutes after open
    if no_trade_opening_minutes > 0:
        now_msk = _msk_now()
        session_open_t, _session_end_t = current_session_bounds(session_type)
        if session_open_t is not None:
            session_open = now_msk.replace(
                hour=session_open_t.hour, minute=session_open_t.minute, second=0, microsecond=0
            )
            minutes_since_open = (now_msk - session_open).total_seconds() / 60
        else:
            minutes_since_open = 999999
        if 0 < minutes_since_open < no_trade_opening_minutes:
            return Reason(
                code=ReasonCode.SESSION_OPENING_GAP,
                severity=Severity.BLOCK,
                msg=f"Opening gap protection: {minutes_since_open:.0f}m < {no_trade_opening_minutes}m",
            )

    # Too close to session end
    if close_before_end_minutes > 0:
        remaining = minutes_until_session_end(session_type)
        if 0 < remaining < close_before_end_minutes:
            return Reason(
                code=ReasonCode.SESSION_CLOSED,
                severity=Severity.BLOCK,
                msg=f"Too close to session end: {remaining:.0f}m remaining",
            )

    return None


# ─── P5-04: HTF trend ────────────────────────────────────────────────────────

def score_htf_alignment(
    signal_side: str,
    htf_trend: Optional[str],
    htf_bonus: int = 5,
    max_score: int = 5,
) -> tuple[int, "Reason"]:
    """
    P5-04: Bonus score when signal aligns with higher-timeframe trend.
    """
    if htf_trend is None or htf_trend == "flat":
        return max_score // 2, Reason(
            code=ReasonCode.HTF_CONFLICT,
            severity=Severity.WARN,
            msg="HTF trend unknown or flat — reduced confidence",
        )
    aligned = (
        (signal_side == "BUY" and htf_trend == "up")
        or (signal_side == "SELL" and htf_trend == "down")
    )
    if aligned:
        return max_score, Reason(
            code=ReasonCode.HTF_ALIGNED,
            severity=Severity.INFO,
            msg=f"HTF aligned ({htf_trend})",
        )
    return 0, Reason(
        code=ReasonCode.HTF_CONFLICT,
        severity=Severity.WARN,
        msg=f"HTF conflict: signal={signal_side} vs HTF={htf_trend}",
    )

# Alias for backward compatibility (engine.py uses score_volatility_soft)
score_volatility_soft = score_volatility

# Wrapper: engine.py expects (int, Reason), score_levels returns (int, list[Reason])
def score_level_clearance(
    entry: float, tp: float, nearest_level, side: str, max_score: int = 20
):
    score, reasons_list = score_levels(entry, tp, nearest_level, side, max_score)
    reason = reasons_list[0] if reasons_list else Reason(
        code=ReasonCode.LEVEL_UNKNOWN, severity=Severity.INFO, msg="No level reason"
    )
    return score, reason
