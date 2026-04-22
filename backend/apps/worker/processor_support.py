from __future__ import annotations

import logging
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from apps.worker.decision_engine.types import MarketSnapshot
from core.services.geometry_optimizer import optimize_signal_geometry
from core.services.timeframe_engine import align_signal_to_execution, build_higher_tf_continuation_thesis, detect_trend, max_timeframe, normalize_timeframe, resample_candles, select_timeframe_stack_for_regime, timeframe_rank
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


def _build_pre_persist_candidate_payload(*, ticker: str, sig_data: dict, strategy_name: str | None = None, stage: str, block_code: str, block_reason: str) -> dict:
    meta = dict(sig_data.get('meta') or {})
    return {
        'instrument_id': ticker,
        'side': sig_data.get('side'),
        'entry': float(sig_data.get('entry') or 0.0),
        'sl': float(sig_data.get('sl') or 0.0),
        'tp': float(sig_data.get('tp') or 0.0),
        'r': float(sig_data.get('r') or 0.0),
        'strategy_name': strategy_name or meta.get('strategy_name') or meta.get('strategy'),
        'analysis_timeframe': meta.get('analysis_timeframe'),
        'execution_timeframe': meta.get('execution_timeframe'),
        'confirmation_timeframe': meta.get('confirmation_timeframe'),
        'timeframe_selection_reason': meta.get('timeframe_selection_reason'),
        'stage': stage,
        'block_code': block_code,
        'block_reason': block_reason,
    }


def _build_review_readiness_seed(sig_data: dict) -> dict:
    meta = dict((sig_data or {}).get('meta') or {})
    thesis = dict(meta.get('higher_tf_thesis') or {}) if isinstance(meta.get('higher_tf_thesis'), dict) else {}
    return {
        'selection_reason': meta.get('timeframe_selection_reason'),
        'thesis_timeframe': meta.get('thesis_timeframe'),
        'execution_timeframe': meta.get('execution_timeframe'),
        'strategy_name': meta.get('strategy_name') or meta.get('strategy'),
        'initial_rr': float((sig_data or {}).get('r') or 0.0),
        'thesis_type': thesis.get('thesis_type'),
        'structure': thesis.get('structure'),
        'side': thesis.get('side') or (sig_data or {}).get('side'),
    }


def _build_pre_persist_review_enrichment(sig_data: dict, *, block_reason: str) -> dict:
    meta = dict((sig_data or {}).get('meta') or {})
    thesis = dict(meta.get('higher_tf_thesis') or {}) if isinstance(meta.get('higher_tf_thesis'), dict) else {}
    thesis_tf = str(meta.get('thesis_timeframe') or thesis.get('thesis_timeframe') or '1m')
    rr_value = float((sig_data or {}).get('r') or 0.0)
    tier = 'B' if thesis_tf in {'5m', '15m', '30m', '1h'} and rr_value >= 1.6 else 'C'
    return {
        'review_readiness': _build_review_readiness_seed(sig_data),
        'conviction_profile': {
            'tier': tier,
            'score': None,
            'threshold': None,
            'score_gap': None,
            'tradable': tier == 'B',
            'rescue_eligible': False,
            'blocked_by_pre_persist_gate': True,
            'block_reason': block_reason,
        },
        'decision_merge': {
            'pre_ai_final_decision': 'REJECT',
            'event_merge_reason': block_reason,
            'freshness_reason': None,
            'event_adjusted_score': None,
        },
    }


def _should_queue_capacity_blocked_candidate(sig_data: dict, *, block_reason: str) -> bool:
    if not str(block_reason or '').startswith('Max positions reached'):
        return False
    meta = dict((sig_data or {}).get('meta') or {})
    thesis = dict(meta.get('higher_tf_thesis') or {}) if isinstance(meta.get('higher_tf_thesis'), dict) else {}
    thesis_tf = str(meta.get('thesis_timeframe') or thesis.get('thesis_timeframe') or '1m')
    selection_reason = str(meta.get('timeframe_selection_reason') or '')
    rr_value = float((sig_data or {}).get('r') or 0.0)
    return thesis_tf in {'5m', '15m'} and selection_reason in {'requested', 'confirmation'} and rr_value >= 2.0


def _build_pending_review_outcome_seed(sig_data: dict, *, trade_mode: str) -> dict:
    review = _build_review_readiness_seed(sig_data)
    initial_rr = float(review.get('initial_rr') or 0.0)
    thesis_tf = str(review.get('thesis_timeframe') or '1m')
    selection_reason = str(review.get('selection_reason') or '')
    approval_candidate = trade_mode == 'auto_paper' and thesis_tf in {'5m', '15m'} and selection_reason in {'requested', 'confirmation'} and initial_rr >= 2.0
    queue_priority = 0
    if thesis_tf == '15m':
        queue_priority += 30
    elif thesis_tf == '5m':
        queue_priority += 20
    if selection_reason == 'requested':
        queue_priority += 20
    elif selection_reason == 'confirmation':
        queue_priority += 15
    if review.get('thesis_type') == 'continuation':
        queue_priority += 10
    elif review.get('thesis_type') == 'timeframe_signal':
        queue_priority += 8
    queue_priority += min(int(initial_rr * 10), 30)
    if approval_candidate:
        queue_priority += 25
    return {
        **review,
        'queue_priority': queue_priority,
        'approval_candidate': approval_candidate,
        'approval_reason': 'higher_tf_strong_pending_candidate' if approval_candidate else 'review_only_pending_candidate',
    }


def _reconcile_review_readiness(review_readiness: dict | None, conviction_profile: dict | None) -> dict:
    review = dict(review_readiness or {})
    conviction = dict(conviction_profile or {})
    if not review:
        return review
    if review.get('approval_candidate') and (conviction.get('has_blockers') or conviction.get('economic_filter_valid') is False or str(conviction.get('tier') or 'C') == 'C'):
        review['approval_candidate'] = False
        review['approval_reason'] = 'demoted_after_decision_flow'
    return review


def _should_relax_governor_suppression(*, sig_meta: dict, perf_governor: dict) -> bool:
    if not bool((perf_governor or {}).get('suppressed')):
        return False
    thesis = dict((sig_meta or {}).get('higher_tf_thesis') or {}) if isinstance((sig_meta or {}).get('higher_tf_thesis'), dict) else {}
    thesis_tf = str((sig_meta or {}).get('thesis_timeframe') or thesis.get('thesis_timeframe') or '1m')
    conviction = dict((sig_meta or {}).get('conviction_profile') or {})
    if thesis_tf not in {'5m', '15m', '30m', '1h'}:
        return False
    if str(conviction.get('tier') or 'C') not in {'B', 'A', 'A+'}:
        return False
    score_gap = conviction.get('score_gap')
    try:
        score_gap_value = int(score_gap)
    except Exception:
        return False
    return score_gap_value >= -10


def _evaluate_selective_policy_throttle(*, policy_state: Any, final_decision: str, score: int, threshold: int, sig_data: dict, perf_governor: dict, freshness_meta: dict) -> tuple[bool, str]:
    if not bool(getattr(policy_state, 'selective_throttle', False)):
        return False, ''
    meta = dict(((sig_data or {}).get('meta') or {}))
    promotion_meta = dict(meta.get('high_conviction_promotion') or {})
    conviction_meta = dict(meta.get('conviction_profile') or {})
    cooldown_meta = dict(meta.get('cooldown_context') or {})
    higher_tf_thesis = dict(meta.get('higher_tf_thesis') or {}) if isinstance(meta.get('higher_tf_thesis'), dict) else {}
    higher_tf_led = str(meta.get('thesis_timeframe') or higher_tf_thesis.get('thesis_timeframe') or '1m') in {'5m', '15m', '30m', '1h'}
    higher_tf_type = str(higher_tf_thesis.get('thesis_type') or '')
    selection_reason = str(meta.get('timeframe_selection_reason') or '')
    promoted = bool(promotion_meta.get('promoted'))
    rr_value = float(sig_data.get('r') or 0.0)
    confidence_bias = int((meta.get('review_readiness') or {}).get('confidence_bias') or 0) if isinstance(meta.get('review_readiness'), dict) else 0
    tradeable_higher_tf = higher_tf_led and str(conviction_meta.get('tier') or 'C') in {'B', 'A', 'A+'} and conviction_meta.get('economic_filter_valid') is not False and not bool(conviction_meta.get('has_blockers'))
    if bool((freshness_meta or {}).get('blocked')):
        return True, 'selective throttle rejects stale candidates during frozen mode'
    if str(final_decision or '').upper() != 'TAKE':
        if higher_tf_led and higher_tf_type in {'continuation', 'timeframe_signal', 'context_alignment'} and not bool((perf_governor or {}).get('suppressed')) and int(score or 0) >= max(int(threshold or 0) - 10, 0) and rr_value >= 1.6:
            return False, ''
        if tradeable_higher_tf and selection_reason in {'requested', 'confirmation'} and not bool((perf_governor or {}).get('suppressed')) and int(score or 0) >= max(int(threshold or 0) - 14, 0) and rr_value >= 1.4 and confidence_bias >= 6:
            return False, ''
        return True, 'selective throttle keeps only TAKE candidates during frozen mode'
    min_score = int(threshold or 0)
    if not promoted:
        buffer_override = conviction_meta.get('frozen_score_buffer_override')
        if buffer_override is not None:
            min_score += int(buffer_override)
        else:
            min_score += int(getattr(policy_state, 'selective_min_score_buffer', 0) or 0)
    if bool(cooldown_meta.get('active')):
        min_score += 2
    if str(final_decision or '').upper() == 'TAKE' and promoted and tradeable_higher_tf and int(score or 0) >= max(int(threshold or 0) - 20, 0) and rr_value >= 1.25:
        return False, ''
    if int(score or 0) < min_score:
        return True, f'selective throttle requires score >= {min_score}'
    min_rr = float(getattr(policy_state, 'selective_min_rr', 0.0) or 0.0)
    rr_override = conviction_meta.get('frozen_rr_override')
    if rr_override is not None:
        min_rr = min(min_rr, float(rr_override))
    if bool(cooldown_meta.get('active')):
        min_rr = max(min_rr, 1.8)
    if rr_value < min_rr:
        return True, f'selective throttle requires RR >= {min_rr:.2f}'
    if bool(getattr(policy_state, 'selective_require_governor_pass', False)) and bool((perf_governor or {}).get('suppressed')):
        return True, 'selective throttle requires governor-pass slice'
    return False, ''


def _build_conviction_profile(*, final_decision: str, score: int, threshold: int, evaluation: Any, perf_governor: dict, freshness_meta: dict, signal_meta: dict | None = None) -> dict:
    reasons = list(getattr(evaluation, 'reasons', []) or [])
    metrics = dict(getattr(evaluation, 'metrics', {}) or {})
    signal_meta = dict(signal_meta or {})
    reason_codes = set()
    for reason in reasons:
        code = getattr(reason, 'code', None)
        if hasattr(code, 'value'):
            reason_codes.add(str(code.value))
        elif code is not None:
            reason_codes.add(str(code))

    block_present = any(getattr(reason, 'severity', None) == 'block' or getattr(getattr(reason, 'severity', None), 'value', None) == 'block' for reason in reasons)
    suppressed = bool((perf_governor or {}).get('suppressed'))
    freshness_blocked = bool((freshness_meta or {}).get('blocked'))
    economic_valid = metrics.get('economic_filter_valid') is True
    net_rr = float(metrics.get('net_rr') or 0.0)
    commission_ratio_raw = metrics.get('commission_dominance_ratio')
    commission_ratio = float(commission_ratio_raw) if commission_ratio_raw is not None else None
    score_gap = int(score or 0) - int(threshold or 0)
    level_too_close = 'LEVEL_TOO_CLOSE' in reason_codes
    volume_anomalous = 'VOLUME_ANOMALOUS' in reason_codes
    higher_tf_thesis = dict(signal_meta.get('higher_tf_thesis') or {}) if isinstance(signal_meta.get('higher_tf_thesis'), dict) else {}
    higher_tf_led = str(signal_meta.get('thesis_timeframe') or higher_tf_thesis.get('thesis_timeframe') or '1m') in {'5m', '15m', '30m', '1h'}
    higher_tf_selection_reason = str(signal_meta.get('timeframe_selection_reason') or '')
    review_readiness = dict(signal_meta.get('review_readiness') or {}) if isinstance(signal_meta.get('review_readiness'), dict) else {}
    confidence_bias = int(review_readiness.get('confidence_bias') or 0)

    tier = 'C'
    frozen_score_buffer_override = None
    frozen_rr_override = None

    if not suppressed and not freshness_blocked and not block_present and economic_valid and net_rr > 0:
        if score_gap >= 10 and net_rr >= 1.0 and (commission_ratio is None or commission_ratio <= 1.0) and not level_too_close and not volume_anomalous:
            tier = 'A+'
            frozen_score_buffer_override = 0
            frozen_rr_override = 1.35
        elif score_gap >= 4 and net_rr >= 0.85 and (commission_ratio is None or commission_ratio <= 1.25):
            tier = 'A'
            frozen_score_buffer_override = 0
            frozen_rr_override = 1.4
        elif score_gap >= 0 and net_rr >= 0.75 and (commission_ratio is None or commission_ratio <= 1.0):
            tier = 'B'
            frozen_score_buffer_override = 0
            frozen_rr_override = 1.5
        elif higher_tf_led and score_gap >= -10 and net_rr >= 0.8 and (commission_ratio is None or commission_ratio <= 1.05):
            tier = 'B'
            frozen_score_buffer_override = 0
            frozen_rr_override = 1.5
        elif higher_tf_selection_reason in {'requested', 'confirmation'} and higher_tf_led and score_gap >= -30 and net_rr >= 1.2 and (commission_ratio is None or commission_ratio <= 0.75):
            tier = 'B'
            frozen_score_buffer_override = 0
            frozen_rr_override = 1.5
        elif confidence_bias >= 15 and higher_tf_selection_reason in {'requested', 'confirmation'} and higher_tf_led and score_gap >= -16 and net_rr >= 1.0 and (commission_ratio is None or commission_ratio <= 0.8):
            tier = 'B'
            frozen_score_buffer_override = 0
            frozen_rr_override = 1.45

    tradable = tier in {'A+', 'A', 'B'}
    decision_upper = str(final_decision or '').upper()
    rescue_eligible = decision_upper in {'SKIP', 'REJECT'} and tradable
    allocator_priority_bonus = 1.15 if tier == 'A+' else (1.08 if tier == 'A' else 1.0)
    if confidence_bias > 0 and tradable:
        allocator_priority_bonus = round(min(1.25, allocator_priority_bonus + min(confidence_bias / 100.0, 0.15)), 4)
    return {
        'tier': tier,
        'tradable': tradable,
        'rescue_eligible': rescue_eligible,
        'score': int(score or 0),
        'threshold': int(threshold or 0),
        'score_gap': int(score_gap),
        'net_rr': round(net_rr, 4),
        'commission_dominance_ratio': round(float(commission_ratio), 4) if commission_ratio is not None else None,
        'economic_filter_valid': economic_valid,
        'blocked_by_governor': suppressed,
        'blocked_by_freshness': freshness_blocked,
        'has_blockers': block_present,
        'frozen_score_buffer_override': frozen_score_buffer_override,
        'frozen_rr_override': frozen_rr_override,
        'allocator_priority_bonus': allocator_priority_bonus,
        'risk_tier_bias': 1.05 if tier == 'A+' else (1.02 if tier == 'A' else (0.97 if tier == 'C' else 1.0)),
        'confidence_bias': confidence_bias,
    }


def _promote_high_conviction_skip(*, final_decision: str, score: int, threshold: int, evaluation: Any, perf_governor: dict, freshness_meta: dict, conviction_profile: dict | None = None) -> tuple[str, str, dict]:
    if str(final_decision or '').upper() not in {'SKIP', 'REJECT'}:
        return final_decision, '', {'promoted': False, 'reason': 'final decision not skip/reject'}
    profile = dict(conviction_profile or _build_conviction_profile(
        final_decision=final_decision,
        score=score,
        threshold=threshold,
        evaluation=evaluation,
        perf_governor=perf_governor,
        freshness_meta=freshness_meta,
    ))
    if not bool(profile.get('rescue_eligible')):
        return final_decision, '', {'promoted': False, 'reason': profile.get('tier') or 'not rescue eligible'}

    promotion_meta = {
        'promoted': True,
        'promotion': 'high_conviction_skip_to_take',
        'tier': profile.get('tier'),
        'score': int(score or 0),
        'threshold': int(threshold or 0),
        'promotion_floor_score': int(threshold or 0),
        'net_rr': profile.get('net_rr'),
        'reason': 'high-conviction skip promoted to TAKE',
    }
    return 'TAKE', 'high-conviction promotion', promotion_meta




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
    confirmation_tf = normalize_timeframe((adaptive_plan or {}).get('confirmation_timeframe') or getattr(settings, 'higher_timeframe', '15m') or '15m', '15m')
    adaptive = dict(adaptive_plan or {})
    regime_name = str(adaptive.get('regime') or 'balanced')
    regime_stack = select_timeframe_stack_for_regime({
        'trend_strength': float(adaptive.get('trend_strength') or (0.82 if regime_name in {'trend', 'expansion_trend'} else (0.22 if regime_name in {'compression', 'chop', 'balanced'} else 0.55))),
        'noise_ratio': float(adaptive.get('noise_ratio') or (0.20 if regime_name in {'trend', 'expansion_trend'} else (0.80 if regime_name in {'risk_off_shock', 'event_burst'} else 0.38))),
        'event_pressure': float(adaptive.get('event_pressure') or (0.92 if regime_name in {'event_burst', 'risk_off_shock', 'catalyst_follow_through'} else 0.05)),
        'instrument_class': str(adaptive.get('instrument_class') or 'equity'),
    })
    allowed_tfs: list[str] = []
    for tf in list(regime_stack.get('thesis_timeframes') or []) + [str(regime_stack.get('execution_timeframe') or '1m')]:
        tf_norm = normalize_timeframe(tf, '1m')
        if tf_norm not in allowed_tfs:
            allowed_tfs.append(tf_norm)
    attempted_tfs = _candidate_timeframes(adaptive_plan, settings, rescue_hint=rescue_hint)
    best_candidate: tuple[float, dict, list[dict], str, str] | None = None
    for tf in attempted_tfs:
        if tf not in allowed_tfs:
            continue
        history = resample_candles(base_history, tf) if tf != '1m' else list(base_history)
        candidate_row = {'timeframe': tf, 'history_len': len(history), 'signal_found': False}
        if len(history) < strategy.lookback:
            candidate_row['skip_reason'] = 'history_too_short'
            candidate_row['required_lookback'] = int(strategy.lookback)
            candidates_meta.append(candidate_row)
            continue
        try:
            signal = strategy.analyze(ticker, history)
        except Exception:
            logger.exception('Strategy %s crashed for %s on %s', getattr(strategy, 'name', 'unknown'), ticker, tf)
            candidate_row['skip_reason'] = 'strategy_exception'
            candidates_meta.append(candidate_row)
            continue
        if not signal and tf != '1m':
            thesis = build_higher_tf_continuation_thesis(history, timeframe=tf)
            if thesis:
                close_px = float((history[-1] or {}).get('close') or 0.0)
                atr_like = max(close_px * 0.006, 1e-6)
                side = str(thesis.get('side') or 'BUY').upper()
                sl = close_px - atr_like * 2.0 if side == 'BUY' else close_px + atr_like * 2.0
                tp = close_px + atr_like * 3.2 if side == 'BUY' else close_px - atr_like * 3.2
                signal = {
                    'instrument_id': ticker,
                    'side': side,
                    'entry': close_px,
                    'sl': sl,
                    'tp': tp,
                    'r': 1.6,
                    'meta': {
                        'strategy': f'higher_tf_{thesis.get("thesis_type")}',
                        'higher_tf_thesis': thesis,
                    },
                }
        candidate_row['signal_found'] = bool(signal)
        if not signal:
            candidate_row['skip_reason'] = 'no_signal'
        if signal:
            meta = dict(signal.get('meta') or {})
            meta['analysis_timeframe'] = tf
            meta['analysis_requested_timeframe'] = requested
            meta['timeframe_selection_reason'] = 'requested' if tf == requested else ('rescue_hint' if rescue_hint and tf == rescue_hint else 'fallback')
            meta['analysis_candles_used'] = len(history)
            signal['meta'] = meta
            rr = float(signal.get('r') or 0.0)
            timeframe_bias = 0.35 if tf == requested and tf != '1m' else (0.25 if tf == confirmation_tf and tf != '1m' else (0.15 if tf != regime_stack.get('execution_timeframe') else 0.0))
            strategy_bias = 0.05 if str(meta.get('strategy') or '').startswith('breakout') else 0.0
            score = rr + timeframe_bias + strategy_bias
            candidate_row['rr'] = round(rr, 4)
            candidate_row['ranking_score'] = round(score, 4)
            selection_reason = 'requested' if tf == requested else ('confirmation' if tf == confirmation_tf else ('rescue_hint' if rescue_hint and tf == rescue_hint else ('execution_fallback' if tf == '1m' else 'fallback')))
            if best_candidate is None or score > best_candidate[0]:
                best_candidate = (score, signal, history, tf, selection_reason)
        candidates_meta.append(candidate_row)
    if best_candidate is not None:
        _, signal, history, tf, selection_reason = best_candidate
        meta = dict(signal.get('meta') or {})
        promoted_thesis_tf = tf
        higher_tf_thesis = dict(meta.get('higher_tf_thesis') or {}) if isinstance(meta.get('higher_tf_thesis'), dict) else None
        if tf == '1m' and confirmation_tf != '1m':
            confirmation_history = resample_candles(base_history, confirmation_tf)
            if confirmation_history:
                trend, slope = detect_trend(confirmation_history)
                side = str(signal.get('side') or 'BUY').upper()
                aligned = (trend == 'up' and side == 'BUY') or (trend == 'down' and side == 'SELL')
                if aligned and abs(float(slope or 0.0)) >= 0.5:
                    promoted_thesis_tf = confirmation_tf
                    selection_reason = 'context_promoted_thesis'
                    higher_tf_thesis = build_higher_tf_continuation_thesis(confirmation_history, timeframe=confirmation_tf) or {
                        'side': side,
                        'thesis_timeframe': confirmation_tf,
                        'thesis_type': 'context_alignment',
                        'structure': f'{trend}_context_alignment',
                    }
        elif tf != '1m':
            higher_tf_thesis = build_higher_tf_continuation_thesis(history, timeframe=tf) or {
                'side': str(signal.get('side') or 'BUY').upper(),
                'thesis_timeframe': tf,
                'thesis_type': 'timeframe_signal',
                'structure': f'{selection_reason}_timeframe_signal',
            }
        meta['timeframe_selection_reason'] = selection_reason
        meta['context_timeframe'] = str(regime_stack.get('context_timeframe') or confirmation_tf)
        meta['thesis_timeframe'] = promoted_thesis_tf
        meta['higher_tf_thesis'] = higher_tf_thesis
        meta['execution_timeframe'] = str(regime_stack.get('execution_timeframe') or '1m')
        meta['higher_timeframe'] = confirmation_tf if tf == '1m' else max_timeframe(tf, confirmation_tf)
        meta['market_regime_profile'] = regime_stack.get('market_regime_profile')
        meta['analysis_timeframe'] = tf
        meta['timeframe_competition'] = {
            'requested_timeframe': requested,
            'confirmation_timeframe': confirmation_tf,
            'attempted_timeframes': list(attempted_tfs),
            'allowed_timeframes': list(allowed_tfs),
            'selected_timeframe': tf,
            'thesis_timeframe': promoted_thesis_tf,
            'selection_reason': selection_reason,
            'candidates': candidates_meta,
        }
        signal['meta'] = meta
        return signal, history, {'candidates': candidates_meta, 'selected_timeframe': tf, 'requested_timeframe': requested, 'confirmation_timeframe': confirmation_tf}
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
