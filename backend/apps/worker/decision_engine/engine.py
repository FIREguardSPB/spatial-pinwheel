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
from core.risk.economic import EconomicFilter, EconomicFilterConfig
from core.services.sector_filters import apply_sector_overrides

try:
    from core.storage.models import Settings
except Exception:  # pragma: no cover - lightweight test stubs
    class Settings:  # type: ignore[override]
        pass

logger = logging.getLogger(__name__)


def _find_nearest_opposing_level(entry: float, side: str, highs: list[float], lows: list[float], atr: float | None, lookback_bars: int) -> tuple[float | None, float, str]:
    """Find nearest opposing level with a strict pass and a tolerance fallback."""
    tol = max(abs(entry) * 0.0005, (atr or 0.0) * 0.15, 1e-6)
    if side == "BUY":
        search = highs[-lookback_bars:] if lookback_bars > 0 else highs
        strict = [h for h in search if h > entry]
        if strict:
            return min(strict), tol, "strict"
        tolerant = [h for h in search if h >= entry - tol]
        if tolerant:
            return max(tolerant), tol, "tolerance"
        return None, tol, "none"

    search = lows[-lookback_bars:] if lookback_bars > 0 else lows
    strict = [l for l in search if l < entry]
    if strict:
        return max(strict), tol, "strict"
    tolerant = [l for l in search if l <= entry + tol]
    if tolerant:
        return min(tolerant), tol, "tolerance"
    return None, tol, "none"




def _strategy_profile(signal: Any) -> dict[str, float]:
    meta = dict(getattr(signal, 'meta', {}) or {})
    requested = meta.get('strategy_name') or meta.get('strategy')
    strategy_name = str(requested or '').strip().lower()
    profiles = {
        'neutral': {'regime': 1.00, 'volatility': 1.00, 'momentum': 1.00, 'levels': 1.00, 'costs': 1.00, 'volume': 1.00, 'threshold_offset': 0},
        'breakout': {'regime': 1.10, 'volatility': 1.00, 'momentum': 1.00, 'levels': 0.95, 'costs': 1.00, 'volume': 1.05, 'threshold_offset': 0},
        'mean_reversion': {'regime': 0.60, 'volatility': 1.05, 'momentum': 0.90, 'levels': 1.25, 'costs': 1.10, 'volume': 0.90, 'threshold_offset': -6},
        'vwap_bounce': {'regime': 0.85, 'volatility': 1.00, 'momentum': 0.95, 'levels': 1.10, 'costs': 1.00, 'volume': 1.25, 'threshold_offset': 2},
    }
    if not strategy_name:
        profile = profiles['neutral'].copy()
        profile['name'] = 'neutral'
        return profile
    profile = profiles.get(strategy_name, profiles['breakout']).copy()
    profile['name'] = strategy_name
    return profile

def _get_w(val, default: int) -> int:
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _weighted_component(raw_weight: Any, default: int, multiplier: float) -> int:
    base = _get_w(raw_weight, default)
    if base <= 0:
        return 0
    return max(1, int(round(base * float(multiplier or 1.0))))


def _adaptive_plan(signal: Any) -> dict[str, Any]:
    meta = dict(getattr(signal, 'meta', {}) or {})
    return dict(meta.get('adaptive_plan') or {})


def _setting_number(settings: object, name: str, default: float) -> float:
    value = getattr(settings, name, None)
    if value is None:
        return float(default)
    return float(value)


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
                                  _get_w(getattr(self.settings, 'decision_threshold', None), 70), reasons, metrics)

        # ── 2. Data sufficiency ───────────────────────────────────────────────
        signal_meta = dict(getattr(signal, 'meta', {}) or {}) if hasattr(signal, 'meta') else {}
        thesis_timeframe = str(signal_meta.get('thesis_timeframe') or '1m')
        min_candles = 38 if thesis_timeframe in {'15m', '30m', '1h'} else (40 if thesis_timeframe == '5m' else 50)
        metrics['min_candles_required'] = min_candles
        if len(snapshot.candles) < min_candles:
            reasons.append(Reason(
                code=ReasonCode.NO_MARKET_DATA, severity=Severity.BLOCK,
                msg=f"Not enough candles ({len(snapshot.candles)})",
            ))
            return self._finalize(Decision.REJECT, 0, 0, 0,
                                  _get_w(getattr(self.settings, 'decision_threshold', None), 70), reasons, metrics)

        # ── P5-03: Session filter ──────────────────────────────────────────────
        no_trade_opening = _get_w(getattr(self.settings, 'no_trade_opening_minutes', 10), 10)
        close_before = _get_w(getattr(self.settings, 'close_before_session_end_minutes', 10), 10)
        session_mode = (
            getattr(self.settings, 'trading_session', None)
            or getattr(self.settings, 'session_type', None)
            or 'all'
        )
        session_block = rules.check_session(
            no_trade_opening_minutes=no_trade_opening,
            close_before_end_minutes=close_before,
            session_type=session_mode,
        )
        if session_block:
            reasons.append(session_block)
            return self._finalize(Decision.REJECT, 0, 0, 0,
                                  _get_w(getattr(self.settings, 'decision_threshold', None), 70), reasons, metrics)

        # ── 3. Prepare indicators ─────────────────────────────────────────────
        closes  = [indicators.to_float(c["close"])  for c in snapshot.candles]
        highs   = [indicators.to_float(c["high"])   for c in snapshot.candles]
        lows    = [indicators.to_float(c["low"])    for c in snapshot.candles]
        volumes = [float(c.get("volume", 0))         for c in snapshot.candles]

        ema_period = 50
        if thesis_timeframe in {'15m', '30m', '1h'} and len(closes) >= 38:
            ema_period = 34
        elif thesis_timeframe == '5m' and len(closes) >= 40:
            ema_period = 34
        metrics['ema_period_used'] = ema_period
        ema50      = indicators.calc_ema(closes, ema_period)
        ema50_prev = indicators.calc_ema(closes[:-1], min(ema_period, max(1, len(closes) - 1)))
        rsi14      = indicators.calc_rsi(closes, 14)
        atr14      = indicators.calc_atr(highs, lows, closes, 14)
        macd_tuple = indicators.calc_macd(closes)

        # P5-01: New indicators
        bb         = indicators.calc_bollinger(closes, 20, 2.0)   # (upper, mid, lower)
        stoch      = indicators.calc_stochastic(highs, lows, closes, 14, 3)  # (%K, %D)
        vol_ratio  = indicators.calc_volume_ratio(volumes, 20)
        vwap       = indicators.calc_vwap(highs, lows, closes, volumes)

        stop_atr_ratio = (abs(float(signal.entry) - float(signal.sl)) / atr14) if atr14 and atr14 > 0 else None
        metrics.update({
            "ema50": ema50, "rsi14": rsi14, "atr14": atr14,
            "macd_hist": macd_tuple[2] if macd_tuple else None,
            "bb_upper": bb[0] if bb else None,
            "bb_lower": bb[2] if bb else None,
            "stoch_k": stoch[0] if stoch else None,
            "stoch_d": stoch[1] if stoch else None,
            "vol_ratio": vol_ratio,
            "vwap": vwap,
            "stop_atr_ratio": round(stop_atr_ratio, 4) if stop_atr_ratio is not None else None,
        })

        if any(v is None for v in (ema50, rsi14, atr14, macd_tuple)):
            reasons.append(Reason(
                code=ReasonCode.NO_MARKET_DATA, severity=Severity.BLOCK,
                msg="Core indicators unavailable",
            ))
            return self._finalize(Decision.REJECT, 0, 0, 0,
                                  _get_w(getattr(self.settings, 'decision_threshold', None), 70), reasons, metrics)

        # ── 4. R/R hard reject ────────────────────────────────────────────────
        rr_block = rules.check_risk_reward(float(signal.r), _setting_number(self.settings, 'rr_min', 1.5))
        if rr_block:
            reasons.append(rr_block)
            return self._finalize(Decision.REJECT, 0, 0, 0,
                                  _get_w(getattr(self.settings, 'decision_threshold', None), 70), reasons, metrics)

        # ── 5. Hard volatility reject ──────────────────────────────────────────
        vol_hard = rules.check_volatility_hard(
            float(signal.entry), float(signal.sl), atr14,
            _setting_number(self.settings, 'atr_stop_hard_min', 0.3),
            _setting_number(self.settings, 'atr_stop_hard_max', 5.0),
        )
        if vol_hard:
            reasons.append(vol_hard)
            return self._finalize(Decision.REJECT, 0, 0, 0,
                                  _get_w(getattr(self.settings, 'decision_threshold', None), 70), reasons, metrics)

        # ── 6. Scoring ────────────────────────────────────────────────────────
        total_score = 0

        profile = _strategy_profile(signal)
        adaptive_plan = _adaptive_plan(signal)
        sector_filters = apply_sector_overrides(self.settings, getattr(signal, 'instrument_id', None))
        if adaptive_plan:
            metrics['adaptive_plan'] = adaptive_plan
        metrics['sector_filters'] = sector_filters
        metrics["strategy_profile"] = profile

        w_regime  = _weighted_component(getattr(self.settings, 'w_regime', None), 20, profile.get("regime", 1.0))
        w_vol     = _weighted_component(getattr(self.settings, 'w_volatility', None), 15, profile.get("volatility", 1.0))
        w_mom     = _weighted_component(getattr(self.settings, 'w_momentum', None), 15, profile.get("momentum", 1.0))
        w_levels  = _weighted_component(getattr(self.settings, 'w_levels', None), 20, profile.get("levels", 1.0))
        w_costs   = _weighted_component(getattr(self.settings, 'w_costs', None), 15, profile.get("costs", 1.0))
        w_volume  = _weighted_component(getattr(self.settings, 'w_volume', None), 0, profile.get("volume", 1.0))  # P5-02

        # A) Regime (EMA trend)
        s, r = rules.score_regime(
            closes[-1], ema50, ema50_prev or ema50, signal.side, max_score=w_regime
        )
        total_score += s; reasons.extend(r)

        # B) Volatility (ATR sanity soft)
        s, r = rules.score_volatility_soft(
            float(signal.entry), float(signal.sl), atr14,
            float((sector_filters or {}).get('atr_stop_soft_min') or _setting_number(self.settings, 'atr_stop_soft_min', 0.6)),
            float((sector_filters or {}).get('atr_stop_soft_max') or _setting_number(self.settings, 'atr_stop_soft_max', 2.5)),
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

        # D) Levels (nearest opposing S/R, excluding current bar)
        level_lookback_bars = max(21, int(getattr(self.settings, 'level_lookback_bars', 55) or 55))
        lookback_highs = highs[-(level_lookback_bars + 1):-1] if len(highs) > 1 else []
        lookback_lows = lows[-(level_lookback_bars + 1):-1] if len(lows) > 1 else []
        entry_f = float(signal.entry)
        nearest, level_tolerance, level_source = _find_nearest_opposing_level(
            entry_f, signal.side, lookback_highs, lookback_lows, atr14, level_lookback_bars
        )
        tp_dist = abs(float(signal.tp) - entry_f)
        level_ratio = (abs(nearest - entry_f) / tp_dist) if nearest is not None and tp_dist > 0 else None
        metrics["nearest_level"] = round(nearest, 6) if nearest is not None else None
        metrics["level_clearance_ratio"] = round(level_ratio, 4) if level_ratio is not None else None
        metrics["level_lookback_bars"] = level_lookback_bars
        metrics["level_search_tolerance"] = round(level_tolerance, 6)
        metrics["level_source"] = level_source
        s, r = rules.score_level_clearance(
            entry_f, float(signal.tp), nearest, signal.side, max_score=w_levels
        )
        total_score += s; reasons.append(r)

        # E) Costs / expectancy
        fees = _setting_number(self.settings, 'fees_bps', 3)
        slip = _setting_number(self.settings, 'slippage_bps', 5)
        s, r, costs = rules.score_costs(
            float(signal.entry), float(signal.sl), float(signal.tp), fees, slip, max_score=w_costs
        )
        total_score += s; reasons.extend(r)
        metrics.update({
            "costs_fee_bps": fees,
            "costs_slippage_bps": slip,
            "gross_rr": round(costs["gross_rr"], 4) if costs.get("gross_rr") is not None else None,
            "net_rr": round(costs["net_rr"], 4) if costs.get("net_rr") is not None else None,
            "raw_profit": round(costs["raw_profit"], 6),
            "raw_loss": round(costs["raw_loss"], 6),
            "round_trip_cost": round(costs["round_trip_cost"], 6),
            "net_profit": round(costs["net_profit"], 6),
            "net_loss": round(costs["net_loss"], 6),
        })

        econ_filter = EconomicFilter(EconomicFilterConfig(
            min_sl_distance_pct=_setting_number(self.settings, 'min_sl_distance_pct', 0.08),
            min_profit_after_costs_multiplier=_setting_number(self.settings, 'min_profit_after_costs_multiplier', 1.25),
            min_trade_value_rub=_setting_number(self.settings, 'min_trade_value_rub', 10.0),
            min_instrument_price_rub=_setting_number(self.settings, 'min_instrument_price_rub', 0.001),
            min_tick_floor_rub=_setting_number(self.settings, 'min_tick_floor_rub', 0.0),
            commission_dominance_warn_ratio=_setting_number(self.settings, 'commission_dominance_warn_ratio', 0.30),
            volatility_sl_floor_multiplier=_setting_number(self.settings, 'volatility_sl_floor_multiplier', 0.0),
            sl_cost_floor_multiplier=_setting_number(self.settings, 'sl_cost_floor_multiplier', 0.0),
        ))
        econ_result = econ_filter.evaluate(
            entry=float(signal.entry),
            sl=float(signal.sl),
            tp=float(signal.tp),
            qty=float(getattr(signal, 'size', 0) or 0),
            fees_bps=fees,
            slippage_bps=slip,
            atr14=atr14,
        )
        metrics.update(econ_result.metrics)
        reasons.extend(econ_result.warnings)

        # F) P5-02: Volume (replaces Liquidity stub)
        if vol_ratio is not None:
            volume_mult = float((sector_filters or {}).get('volume_filter_multiplier') or 1.0)
            min_ratio = max(0.2, 0.5 * volume_mult)
            anomalous_ratio = _setting_number(self.settings, 'volume_anomalous_ratio', 8.0)
            extreme_ratio = _setting_number(self.settings, 'volume_extreme_ratio', 20.0)
            metrics["volume_warn_threshold"] = anomalous_ratio
            metrics["volume_extreme_threshold"] = extreme_ratio
            s, r = rules.score_volume(
                vol_ratio,
                max_score=w_volume,
                min_ratio=min_ratio,
                anomalous_ratio=anomalous_ratio,
                extreme_ratio=extreme_ratio,
            )
            if r.code == ReasonCode.VOLUME_LOW and r.severity == Severity.BLOCK and thesis_timeframe in {'15m', '30m', '1h'} and str(signal_meta.get('timeframe_selection_reason') or '') in {'requested', 'confirmation'}:
                r = Reason(code=ReasonCode.VOLUME_LOW, severity=Severity.WARN, msg=f"{r.msg}; tolerated for higher-TF requested/confirmation setup")
            if r.severity == Severity.BLOCK:
                reasons.append(r)
                return self._finalize(Decision.REJECT, 0, 0, 0,
                                      _get_w(getattr(self.settings, 'decision_threshold', None), 70), reasons, metrics)
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

        adaptive_threshold = adaptive_plan.get('decision_threshold') if adaptive_plan else None
        threshold_pct = int(adaptive_threshold if adaptive_threshold is not None else (_get_w(getattr(self.settings, 'decision_threshold', None), 70) + int(profile.get("threshold_offset", 0) or 0)))
        threshold_pct = max(0, min(100, threshold_pct))
        if adaptive_plan:
            metrics['adaptive_threshold_source'] = 'symbol_plan'
            metrics['adaptive_regime'] = adaptive_plan.get('regime')
            metrics['adaptive_hold_bars'] = adaptive_plan.get('hold_bars')
            metrics['adaptive_risk_multiplier'] = adaptive_plan.get('risk_multiplier')
        decision = Decision.TAKE if score_pct >= threshold_pct else Decision.SKIP

        if not econ_result.is_valid and econ_result.block_reason is not None:
            reasons.append(econ_result.block_reason)
            metrics["decision_adjustment"] = "blocked_economic_filter"
            decision = Decision.REJECT

        net_rr = metrics.get("net_rr")
        if net_rr is not None and net_rr <= 0:
            reasons.append(Reason(
                code=ReasonCode.COSTS_TOO_HIGH,
                severity=Severity.BLOCK,
                msg=f"Net RR {net_rr:.2f} blocks execution",
            ))
            metrics["decision_adjustment"] = "blocked_non_positive_net_rr"
            decision = Decision.REJECT
        elif net_rr is not None and net_rr < 0.75 and decision == Decision.TAKE:
            reasons.append(Reason(
                code=ReasonCode.COSTS_TOO_HIGH,
                severity=Severity.WARN,
                msg=f"Net RR {net_rr:.2f} caps decision to SKIP",
            ))
            metrics["decision_adjustment"] = "capped_take_low_net_rr"
            decision = Decision.SKIP

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
