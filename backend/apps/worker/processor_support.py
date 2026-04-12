from __future__ import annotations

import logging
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from apps.worker.decision_engine.types import MarketSnapshot
from core.services.geometry_optimizer import optimize_signal_geometry
from core.services.timeframe_engine import align_signal_to_execution, detect_trend, normalize_timeframe, resample_candles, timeframe_rank
from core.storage.decision_log_utils import append_decision_log_best_effort
from core.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)

def _apply_event_regime(decision: str, score: int, threshold: int, event_regime: dict | None, *, has_blockers: bool) -> tuple[str, int, str]:
    if not event_regime:
        return decision, score, "no event regime"
    adjusted_score = int(score + int(event_regime.get('score_bias') or 0))
    regime = str(event_regime.get('regime') or 'calm')
    action = str(event_regime.get('action') or 'observe')
    severity = float(event_regime.get('severity') or 0.0)
    block_threshold = float(event_regime.get('block_threshold') or 0.82)

    if has_blockers:
        return decision, adjusted_score, 'DE hard block preserved'
    if action == 'de_risk' and severity >= block_threshold and decision == 'TAKE':
        return 'SKIP', adjusted_score, f'event regime {regime} enforced de-risk'
    if decision != 'TAKE' and adjusted_score >= threshold + 2 and action == 'lean_with_catalyst':
        return 'TAKE', adjusted_score, f'event regime {regime} promoted TAKE'
    if decision == 'TAKE' and adjusted_score < threshold and action in {'trade_smaller', 'de_risk'}:
        return 'SKIP', adjusted_score, f'event regime {regime} demoted weak TAKE'
    return decision, adjusted_score, f'event regime {regime} observed'

def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, SimpleNamespace):
        return _json_safe(vars(value))
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(mode="json"))
    return value


def _append_decision_log(db: Session, *, log_type: str, message: str, payload: dict | None = None) -> None:
    append_decision_log_best_effort(
        log_type=log_type,
        message=message,
        payload=_json_safe(payload or {}),
    )


def _build_merge_payload(*, ticker: str, signal_id: str, evaluation, ai_result, final_decision: str, merge_reason: str, ai_mode: str, ai_min_confidence: int, de_has_blockers: bool) -> dict:
    return {
        "signal_id": signal_id,
        "instrument_id": ticker,
        "ai_mode": ai_mode,
        "de_decision": evaluation.decision.value,
        "de_score": evaluation.score,
        "de_has_blockers": de_has_blockers,
        "de_reason_count": len(evaluation.reasons),
        "ai_decision": getattr(getattr(ai_result, "decision", None), "value", None) if ai_result else None,
        "ai_confidence": getattr(ai_result, "confidence", None) if ai_result else None,
        "ai_provider": getattr(ai_result, "provider", None) if ai_result else None,
        "ai_min_confidence": ai_min_confidence,
        "final_decision": final_decision,
        "merge_reason": merge_reason,
        "ai_prompt_profile": "intraday_dynamic_v3_research_scalp",
    }


def _build_signal_pipeline_payload(*, ticker: str, signal_id: str, sig_data: dict, evaluation, final_decision: str, merge_payload: dict | None, risk_reason: str | None = None) -> dict:
    meta = dict(sig_data.get("meta") or {})
    return {
        "signal_id": signal_id,
        "instrument_id": ticker,
        "side": sig_data.get("side"),
        "entry": float(sig_data.get("entry") or 0),
        "sl": float(sig_data.get("sl") or 0),
        "tp": float(sig_data.get("tp") or 0),
        "r": float(sig_data.get("r") or 0),
        "size": float(sig_data.get("size") or 0),
        "strategy_name": meta.get("strategy_name") or meta.get("strategy") or getattr(getattr(evaluation, "strategy", None), "name", None),
        "analysis_timeframe": meta.get('analysis_timeframe'),
        "execution_timeframe": meta.get('execution_timeframe'),
        "confirmation_timeframe": meta.get('confirmation_timeframe'),
        "strategy_meta": meta,
        "risk_reason": risk_reason,
        "de": evaluation.model_dump(mode="json") if evaluation else None,
        "merge": merge_payload,
        "final_decision": final_decision,
    }




def _apply_geometry_pass(*, db: Session, ticker: str, sig_data: dict, candles: list[dict], settings, adaptive_plan: dict | None, event_regime: dict | None = None, evaluation_metrics: dict | None = None, phase: str = "initial") -> tuple[dict, dict | None]:
    optimized, geometry = optimize_signal_geometry(
        sig_data,
        candles,
        settings,
        adaptive_plan=adaptive_plan,
        event_regime=event_regime,
        evaluation_metrics=evaluation_metrics,
        phase=phase,
    )
    if geometry.applied:
        _append_decision_log(
            db,
            log_type="signal_geometry_optimizer",
            message=f"{ticker} geometry optimized [{phase}]",
            payload={
                "instrument_id": ticker,
                "phase": phase,
                "geometry": geometry.to_meta(),
                "signal": _json_safe(optimized),
            },
        )
    return optimized, geometry.to_meta() if geometry else None


def _build_candles_summary(candles: list[dict]) -> dict:
    """Extract key indicators from candle history for AI context."""
    if not candles:
        return {}
    closes = [float(c["close"]) for c in candles]
    highs  = [float(c["high"])  for c in candles]
    lows   = [float(c["low"])   for c in candles]

    # Simple EMA50
    ema50 = None
    if len(closes) >= 50:
        k = 2 / 51
        ema50 = closes[-50]
        for p in closes[-49:]:
            ema50 = p * k + ema50 * (1 - k)

    # ATR14
    atr14 = None
    if len(candles) >= 15:
        trs = []
        for i in range(1, min(15, len(candles))):
            h, l, pc = highs[-i], lows[-i], closes[-i-1]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr14 = sum(trs) / len(trs)

    # RSI14
    rsi14 = None
    if len(closes) >= 15:
        deltas = [closes[i] - closes[i-1] for i in range(-14, 0)]
        gains = [max(0, d) for d in deltas]
        losses = [max(0, -d) for d in deltas]
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        if avg_loss > 0:
            rs = avg_gain / avg_loss
            rsi14 = round(100 - 100 / (1 + rs), 1)

    return {
        "last_close": closes[-1] if closes else 0,
        "ema50": round(ema50, 4) if ema50 else None,
        "atr14": round(atr14, 4) if atr14 else None,
        "rsi14": rsi14,
        "macd_hist": None,  # would need full MACD calc
    }


def _candidate_timeframes(adaptive_plan: dict | None, settings: Any, *, rescue_hint: str | None = None) -> list[str]:
    requested = normalize_timeframe((adaptive_plan or {}).get('analysis_timeframe') or getattr(settings, 'higher_timeframe', '1m') or '1m', '1m')
    confirmation = normalize_timeframe((adaptive_plan or {}).get('confirmation_timeframe') or getattr(settings, 'higher_timeframe', '15m') or '15m', '15m')
    floor_tf = normalize_timeframe((adaptive_plan or {}).get('analysis_timeframe_floor') or '1m', '1m')
    floor_rank = timeframe_rank(floor_tf)
    ordered: list[str] = []
    for item in [rescue_hint, requested, '5m', '15m', '1m', confirmation]:
        tf = normalize_timeframe(item, '1m') if item else None
        if tf and timeframe_rank(tf) >= floor_rank and tf not in ordered:
            ordered.append(tf)
    return ordered


def _run_strategy_timeframe_search(strategy: BaseStrategy, ticker: str, base_history: list[dict], adaptive_plan: dict | None, settings: Any, *, rescue_hint: str | None = None) -> tuple[dict | None, list[dict], dict]:
    candidates_meta: list[dict] = []
    requested = normalize_timeframe((adaptive_plan or {}).get('analysis_timeframe') or '1m', '1m')
    for tf in _candidate_timeframes(adaptive_plan, settings, rescue_hint=rescue_hint):
        history = resample_candles(base_history, tf) if tf != '1m' else list(base_history)
        if len(history) < strategy.lookback:
            continue
        try:
            signal = strategy.analyze(ticker, history)
        except Exception:
            logger.exception('Strategy %s crashed for %s on %s', getattr(strategy, 'name', 'unknown'), ticker, tf)
            continue
        candidates_meta.append({'timeframe': tf, 'history_len': len(history), 'signal_found': bool(signal)})
        if signal:
            meta = dict(signal.get('meta') or {})
            meta['analysis_timeframe'] = tf
            meta['analysis_requested_timeframe'] = requested
            meta['timeframe_selection_reason'] = 'requested' if tf == requested else ('rescue_hint' if rescue_hint and tf == rescue_hint else 'fallback')
            meta['analysis_candles_used'] = len(history)
            signal['meta'] = meta
            return signal, history, {'candidates': candidates_meta, 'selected_timeframe': tf, 'requested_timeframe': requested}
    return None, list(base_history), {'candidates': candidates_meta, 'selected_timeframe': None, 'requested_timeframe': requested}


def _attach_execution_geometry(sig_data: dict, *, execution_history: list[dict], confirmation_history: list[dict] | None, adaptive_plan: dict | None) -> dict:
    meta = dict(sig_data.get('meta') or {})
    analysis_tf = normalize_timeframe(meta.get('analysis_timeframe') or (adaptive_plan or {}).get('analysis_timeframe') or '1m', '1m')
    execution_tf = normalize_timeframe((adaptive_plan or {}).get('execution_timeframe') or '1m', '1m')
    confirmation_tf = normalize_timeframe((adaptive_plan or {}).get('confirmation_timeframe') or '15m', '15m') if ((adaptive_plan or {}).get('confirmation_timeframe') or execution_tf != analysis_tf) else None
    exec_price = float((execution_history[-1] or {}).get('close') or 0.0) if execution_history else 0.0
    analysis_entry = float(sig_data.get('entry') or 0.0)
    if analysis_tf != execution_tf and exec_price > 0 and analysis_entry > 0:
        meta['analysis_entry_price'] = analysis_entry
        sig_data = align_signal_to_execution(sig_data, exec_price)
        meta['execution_price_anchor'] = exec_price
    if confirmation_history:
        trend, slope = detect_trend(confirmation_history)
        meta['confirmation_timeframe'] = confirmation_tf
        meta['htf_trend'] = trend
        meta['htf_ema_slope'] = slope
    meta['execution_timeframe'] = execution_tf
    sig_data['meta'] = meta
    return sig_data


def _snapshot_for_history(sig_data: dict, analysis_history: list[dict], confirmation_history: list[dict] | None = None) -> MarketSnapshot:
    trend, slope = detect_trend(confirmation_history or []) if confirmation_history else ('flat', None)
    return MarketSnapshot(
        candles=analysis_history,
        last_price=sig_data.get('entry') or analysis_history[-1]['close'],
        htf_trend=None if trend == 'flat' else trend,
        htf_ema_slope=slope,
    )


