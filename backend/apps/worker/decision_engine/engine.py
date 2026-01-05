from decimal import Decimal
from typing import Dict, Any, List
import logging

from apps.worker.decision_engine.types import (
    Decision, DecisionResult, MarketSnapshot, Reason, ReasonCode, Severity
)
from apps.worker.decision_engine import rules, indicators
from core.storage.models import Settings

logger = logging.getLogger(__name__)

class DecisionEngine:
    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate(self, signal: Any, snapshot: MarketSnapshot) -> DecisionResult:
        """
        Evaluate a candidate signal against 200 last candles.
        Returns score (0-100) and Decision (TAKE/SKIP/REJECT).
        """
        reasons: List[Reason] = []
        metrics: Dict[str, Any] = {}
        
        # 1. Hard Rejects (Pre-calc)
        # Risk Limits (TODO: In v1 we assume external risk manager rejected before here, or we check pure signal logic)
        # Invalid Signal
        invalid = rules.check_invalid_signal(
            signal.side, signal.entry, signal.sl, signal.tp, signal.size
        )
        if invalid:
            reasons.append(invalid)
            # Hard Reject -> Score 0
            return self._finalize(Decision.REJECT, 0, 0, 0, int(self.settings.decision_threshold), reasons, metrics)
            
        # Data Sufficiency
        if len(snapshot.candles) < 50:
            reasons.append(Reason(code=ReasonCode.NO_MARKET_DATA, severity=Severity.BLOCK, msg=f"Not enough candles ({len(snapshot.candles)})"))
            return self._finalize(Decision.REJECT, 0, 0, 0, int(self.settings.decision_threshold), reasons, metrics)

        # 2. Prepare Data (Decimal -> Float pure python)
        closes = [indicators.to_float(c["close"]) for c in snapshot.candles]
        highs = [indicators.to_float(c["high"]) for c in snapshot.candles]
        lows = [indicators.to_float(c["low"]) for c in snapshot.candles]
        
        # 3. Calculate Indicators
        ema50 = indicators.calc_ema(closes, 50)
        ema50_prev = indicators.calc_ema(closes[:-1], 50)
        
        rsi14 = indicators.calc_rsi(closes, 14)
        atr14 = indicators.calc_atr(highs, lows, closes, 14)
        
        macd_tuple = indicators.calc_macd(closes) # (line, signal, hist)
        
        if ema50 is None or rsi14 is None or atr14 is None or macd_tuple is None:
             reasons.append(Reason(code=ReasonCode.NO_MARKET_DATA, severity=Severity.BLOCK, msg="Indicators mismatch"))
             return self._finalize(Decision.REJECT, 0, 0, 0, int(self.settings.decision_threshold), reasons, metrics)
             
        # Metrics for Payload
        metrics["ema50"] = ema50
        metrics["rsi14"] = rsi14
        metrics["atr14"] = atr14
        metrics["macd_hist"] = macd_tuple[2]

        # 1.1 More Hard Rejects (Post-Indicators)
        
        # 1.1 More Hard Rejects (Post-Indicators)
        
        # ATR / Stop Logic (P0.2 Configurable)
        vol_hard = rules.check_volatility_hard(
            float(signal.entry), float(signal.sl), atr14,
            min_dist=float(self.settings.atr_stop_hard_min) if self.settings.atr_stop_hard_min is not None else 0.3,
            max_dist=float(self.settings.atr_stop_hard_max) if self.settings.atr_stop_hard_max is not None else 5.0
        )
        if vol_hard:
            reasons.append(vol_hard)
            
        # R Logic (P0.2 Configurable)
        rr_target = float(self.settings.rr_min or 1.5)
        rr_hard = rules.check_risk_reward(float(signal.r), target=rr_target)
        if rr_hard:
            reasons.append(rr_hard)
            
        # If any hard rejects, fail now
        if reasons:
             return self._finalize(Decision.REJECT, 0, 0, 0, int(self.settings.decision_threshold), reasons, metrics)
        
        # 4. Run Soft Gates (Weights)
        total_score = 0
        
        # Helper to allow 0 weight (override None only)
        def _get_w(val, default):
            return int(val) if val is not None else default
            
        w_regime = _get_w(self.settings.w_regime, 20)
        w_vol = _get_w(self.settings.w_volatility, 15)
        w_mom = _get_w(self.settings.w_momentum, 15)
        w_levels = _get_w(self.settings.w_levels, 20)
        w_costs = _get_w(self.settings.w_costs, 15)
        w_liq = _get_w(self.settings.w_liquidity, 5)
        
        
        # A) Regime
        s, r = rules.score_regime(closes[-1], ema50, ema50_prev or ema50, signal.side, max_score=w_regime)
        total_score += s
        reasons.extend(r)
        
        # B) Volatility
        s, r = rules.score_volatility(
            float(signal.entry), float(signal.sl), atr14,
            min_soft=float(self.settings.atr_stop_soft_min) if self.settings.atr_stop_soft_min is not None else 0.6,
            max_soft=float(self.settings.atr_stop_soft_max) if self.settings.atr_stop_soft_max is not None else 2.5,
            max_score=w_vol
        )
        total_score += s
        reasons.extend(r)
        metrics["sl_atr"] = round(abs(float(signal.entry) - float(signal.sl)) / atr14, 2)
        
        # C) Momentum (P0.1 MACD logic)
        s, r = rules.score_momentum(rsi14, macd_tuple[2], signal.side, max_score=w_mom)
        total_score += s
        reasons.extend(r)
        
        # D) Levels
        nearest = None
        window = 50
        entry_val = float(signal.entry)
        
        # Logic: Find nearest level IN THE DIRECTION OF TP? 
        # Ticket says: "nearest level towards TP"
        if signal.side == "BUY":
            # Resistance is ABOVE entry. We want the LOWEST high that is ABOVE entry.
            recent_highs = [h for h in highs[-window:] if h > entry_val]
            if recent_highs:
                nearest = min(recent_highs) # Nearest resistance
        else:
            # Support is BELOW entry. We want the HIGHEST low that is BELOW entry.
            recent_lows = [l for l in lows[-window:] if l < entry_val]
            if recent_lows:
                nearest = max(recent_lows) # Nearest support
                
        if nearest is not None:
            metrics["nearest_level"] = nearest
        else:
             metrics["nearest_level"] = None

        s, r = rules.score_levels(float(signal.entry), float(signal.tp), nearest, signal.side, max_score=w_levels)
        total_score += s
        reasons.extend(r)
        
        # E) Costs
        # Handle None fees (P0.3)
        fees = self.settings.fees_bps if self.settings.fees_bps is not None else 0
        slip = self.settings.slippage_bps if self.settings.slippage_bps is not None else 0
        
        s, r = rules.score_costs(
            float(signal.entry), float(signal.sl), float(signal.tp),
            fees, slip, max_score=w_costs
        )
        total_score += s
        reasons.extend(r)
        
        # F) Liquidity (Stub)
        liq_score = w_liq
        total_score += liq_score
        reasons.append(Reason(code=ReasonCode.LIQUIDITY_UNKNOWN, severity=Severity.WARN, msg="Liquidity assumed (Stub)"))
        
        # 5. Final Decision (P0.6 Normalization)
        
        # Calculate Score Max from Sum of Weights
        # (Must match active weights used above)
        score_max = w_regime + w_vol + w_mom + w_levels + w_costs + w_liq
        
        score_raw = total_score
        score_pct = 0
        if score_max > 0:
            score_pct = int(round((score_raw / score_max) * 100))
        
        # Decision based on Percentage (Strictness Math)
        threshold_pct = int(self.settings.decision_threshold)
        decision = Decision.SKIP
        
        if score_pct >= threshold_pct:
            decision = Decision.TAKE
            
        return self._finalize(decision, score_pct, score_raw, score_max, threshold_pct, reasons, metrics)

    def _finalize(self, decision: Decision, score_pct: int, score_raw: int, score_max: int, threshold_pct: int, reasons: List[Reason], metrics: Dict[str, Any]) -> DecisionResult:
        # Sort reasons: Block > Warn > Info
        order = {Severity.BLOCK: 0, Severity.WARN: 1, Severity.INFO: 2}
        reasons_sorted = sorted(reasons, key=lambda x: (order.get(x.severity, 99), x.code))
        
        return DecisionResult(
            decision=decision,
            score_pct=score_pct,
            threshold_pct=threshold_pct,
            score_raw=score_raw,
            score_max=score_max,
            # Legacy fields - map to normalized pct/threshold
            score=score_pct,
            threshold=threshold_pct,
            reasons=reasons_sorted,
            metrics=metrics
        )
