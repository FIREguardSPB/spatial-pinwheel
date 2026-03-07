"""
DecisionEngine — evaluates trading signals against market conditions.

P5-01: Uses Bollinger, Stochastic, VolumeRatio in scoring
P5-02: Volume filter replaces Liquidity stub
P5-03: Session filter — hard reject outside MOEX hours
P5-04: HTF alignment bonus
"""
from typing import Any, Dict, List
import logging

from apps.worker.decision_engine.types import (
    Decision, DecisionResult, MarketSnapshot, Reason, ReasonCode, Severity,
)
from apps.worker.decision_engine import rules, indicators
from core.storage.models import Settings

logger = logging.getLogger(__name__)


def _get_w(val, default: int) -> int:
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


class DecisionEngine:
    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate(self, signal: Any, snapshot: MarketSnapshot) -> DecisionResult:
        reasons: List[Reason] = []
        metrics: Dict[str, Any] = {}

        # ── 1. Hard reject: invalid signal ───────────────────────────────────
        invalid = rules.check_invalid_signal(
            signal.side, signal.entry, signal.sl, signal.tp, signal.size
        )
        if invalid:
            reasons.append(invalid)
            return self._finalize(Decision.REJECT, 0, 0, 0,
                                  int(self.settings.decision_threshold), reasons, metrics)

        # ── 2. Data sufficiency ───────────────────────────────────────────────
        if len(snapshot.candles) < 50:
            reasons.append(Reason(
                code=ReasonCode.NO_MARKET_DATA, severity=Severity.BLOCK,
                msg=f"Not enough candles ({len(snapshot.candles)})",
            ))
            return self._finalize(Decision.REJECT, 0, 0, 0,
                                  int(self.settings.decision_threshold), reasons, metrics)

        # ── P5-03: Session filter ──────────────────────────────────────────────
        no_trade_opening = _get_w(getattr(self.settings, 'no_trade_opening_minutes', 10), 10)
        close_before = _get_w(getattr(self.settings, 'close_before_session_end_minutes', 10), 10)
        session_block = rules.check_session(
            no_trade_opening_minutes=no_trade_opening,
            close_before_end_minutes=close_before,
        )
        if session_block:
            reasons.append(session_block)
            return self._finalize(Decision.REJECT, 0, 0, 0,
                                  int(self.settings.decision_threshold), reasons, metrics)

        # ── 3. Prepare indicators ─────────────────────────────────────────────
        closes  = [indicators.to_float(c["close"])  for c in snapshot.candles]
        highs   = [indicators.to_float(c["high"])   for c in snapshot.candles]
        lows    = [indicators.to_float(c["low"])    for c in snapshot.candles]
        volumes = [float(c.get("volume", 0))         for c in snapshot.candles]

        ema50      = indicators.calc_ema(closes, 50)
        ema50_prev = indicators.calc_ema(closes[:-1], 50)
        rsi14      = indicators.calc_rsi(closes, 14)
        atr14      = indicators.calc_atr(highs, lows, closes, 14)
        macd_tuple = indicators.calc_macd(closes)

        # P5-01: New indicators
        bb         = indicators.calc_bollinger(closes, 20, 2.0)   # (upper, mid, lower)
        stoch      = indicators.calc_stochastic(highs, lows, closes, 14, 3)  # (%K, %D)
        vol_ratio  = indicators.calc_volume_ratio(volumes, 20)
        vwap       = indicators.calc_vwap(highs, lows, closes, volumes)

        metrics.update({
            "ema50": ema50, "rsi14": rsi14, "atr14": atr14,
            "bb_upper": bb[0] if bb else None,
            "bb_lower": bb[2] if bb else None,
            "stoch_k": stoch[0] if stoch else None,
            "stoch_d": stoch[1] if stoch else None,
            "vol_ratio": vol_ratio,
            "vwap": vwap,
        })

        if any(v is None for v in (ema50, rsi14, atr14, macd_tuple)):
            reasons.append(Reason(
                code=ReasonCode.NO_MARKET_DATA, severity=Severity.BLOCK,
                msg="Core indicators unavailable",
            ))
            return self._finalize(Decision.REJECT, 0, 0, 0,
                                  int(self.settings.decision_threshold), reasons, metrics)

        # ── 4. Hard volatility reject ──────────────────────────────────────────
        vol_hard = rules.check_volatility_hard(
            float(signal.entry), float(signal.sl), atr14,
            float(self.settings.atr_stop_hard_min),
            float(self.settings.atr_stop_hard_max),
        )
        if vol_hard:
            reasons.append(vol_hard)
            return self._finalize(Decision.REJECT, 0, 0, 0,
                                  int(self.settings.decision_threshold), reasons, metrics)

        # ── 5. R/R hard reject ────────────────────────────────────────────────
        rr_block = rules.check_risk_reward(float(signal.r), float(self.settings.rr_min))
        if rr_block:
            reasons.append(rr_block)
            return self._finalize(Decision.REJECT, 0, 0, 0,
                                  int(self.settings.decision_threshold), reasons, metrics)

        # ── 6. Scoring ────────────────────────────────────────────────────────
        total_score = 0

        w_regime  = _get_w(self.settings.w_regime,    20)
        w_vol     = _get_w(self.settings.w_volatility, 15)
        w_mom     = _get_w(self.settings.w_momentum,   15)
        w_levels  = _get_w(self.settings.w_levels,     20)
        w_costs   = _get_w(self.settings.w_costs,      15)
        w_volume  = _get_w(getattr(self.settings, 'w_volume', 10), 10)  # P5-02

        # A) Regime (EMA trend)
        s, r = rules.score_regime(
            closes[-1], ema50, ema50_prev or ema50, signal.side, max_score=w_regime
        )
        total_score += s; reasons.extend(r)

        # B) Volatility (ATR sanity soft)
        s, r = rules.score_volatility_soft(
            float(signal.entry), float(signal.sl), atr14,
            float(self.settings.atr_stop_soft_min),
            float(self.settings.atr_stop_soft_max),
            max_score=w_vol,
        )
        total_score += s; reasons.extend(r)

        # C) Momentum (RSI + MACD)
        s, r = rules.score_momentum(rsi14, macd_tuple[2], signal.side, max_score=w_mom)
        total_score += s; reasons.extend(r)

        # P5-01: Stochastic confirmation on top of RSI
        if stoch:
            sk, sd = stoch
            stoch_aligned = (
                (signal.side == "BUY"  and sk < 80 and sk > sd) or
                (signal.side == "SELL" and sk > 20 and sk < sd)
            )
            if stoch_aligned:
                total_score += 2  # bonus on confirmation
            metrics["stoch_signal"] = "confirm" if stoch_aligned else "neutral"

        # D) Levels (nearest S/R)
        recent = closes[-20:] if len(closes) >= 20 else closes
        nearest = max(recent) if signal.side == "BUY" else min(recent)
        s, r = rules.score_level_clearance(
            float(signal.entry), float(signal.tp), nearest, signal.side, max_score=w_levels
        )
        total_score += s; reasons.append(r)

        # E) Costs
        fees  = float(getattr(self.settings, 'fees_bps', 3))
        slip  = float(getattr(self.settings, 'slippage_bps', 5))
        s, r = rules.score_costs(
            float(signal.entry), float(signal.sl), float(signal.tp), fees, slip, max_score=w_costs
        )
        total_score += s; reasons.extend(r)

        # F) P5-02: Volume (replaces Liquidity stub)
        if vol_ratio is not None:
            min_ratio = 0.5
            anom_ratio = 3.0
            s, r = rules.score_volume(vol_ratio, max_score=w_volume,
                                      min_ratio=min_ratio, anomalous_ratio=anom_ratio)
            if r.severity == Severity.BLOCK:
                reasons.append(r)
                return self._finalize(Decision.REJECT, 0, 0, 0,
                                      int(self.settings.decision_threshold), reasons, metrics)
            total_score += s; reasons.append(r)
        else:
            # No volume data — partial score
            total_score += w_volume // 2
            reasons.append(Reason(code=ReasonCode.LIQUIDITY_UNKNOWN, severity=Severity.WARN,
                                  msg="Volume data unavailable"))

        # G) P5-04: HTF alignment bonus
        if snapshot.htf_trend is not None:
            s, r = rules.score_htf_alignment(signal.side, snapshot.htf_trend, max_score=5)
            total_score += s; reasons.append(r)

        # ── 7. Normalize & decide ──────────────────────────────────────────────
        score_max = w_regime + w_vol + w_mom + w_levels + w_costs + w_volume + (5 if snapshot.htf_trend else 0)
        score_raw = total_score
        score_pct = int(round((score_raw / score_max) * 100)) if score_max > 0 else 0

        threshold_pct = int(self.settings.decision_threshold)
        decision = Decision.TAKE if score_pct >= threshold_pct else Decision.SKIP

        return self._finalize(decision, score_pct, score_raw, score_max,
                              threshold_pct, reasons, metrics)

    def _finalize(self, decision, score_pct, score_raw, score_max,
                  threshold_pct, reasons, metrics) -> DecisionResult:
        order = {Severity.BLOCK: 0, Severity.WARN: 1, Severity.INFO: 2}
        reasons_sorted = sorted(reasons, key=lambda x: (order.get(x.severity, 99), x.code))
        return DecisionResult(
            decision=decision, score_pct=score_pct, threshold_pct=threshold_pct,
            score_raw=score_raw, score_max=score_max,
            score=score_pct, threshold=threshold_pct,
            reasons=reasons_sorted, metrics=metrics,
        )
