from __future__ import annotations

from typing import Any


def ml_overlay_action(ml_overlay: dict[str, Any]) -> str | None:
    action = str(ml_overlay.get('action') or '')
    if action:
        return action
    reason = str(ml_overlay.get('reason') or '')
    if reason == 'ml_take_veto':
        return 'veto'
    if reason == 'ml_boost':
        return 'boost'
    if reason == 'ml_risk_cut':
        return 'cut'
    if reason in {'ml_disabled', 'no_active_model'}:
        return 'unavailable'
    return None


def compact_signal_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    meta = meta or {}
    decision = meta.get('decision') if isinstance(meta.get('decision'), dict) else {}
    auto_policy = meta.get('auto_policy') if isinstance(meta.get('auto_policy'), dict) else {}
    performance_governor = meta.get('performance_governor') if isinstance(meta.get('performance_governor'), dict) else {}
    ai_decision = meta.get('ai_decision') if isinstance(meta.get('ai_decision'), dict) else {}
    ml_overlay = meta.get('ml_overlay') if isinstance(meta.get('ml_overlay'), dict) else {}
    geometry_optimizer = meta.get('geometry_optimizer') if isinstance(meta.get('geometry_optimizer'), dict) else {}
    ai_fast_path = meta.get('ai_fast_path') if isinstance(meta.get('ai_fast_path'), dict) else {}

    compact: dict[str, Any] = {
        'final_decision': meta.get('final_decision'),
        'strategy_name': meta.get('strategy_name'),
        'strategy': meta.get('strategy'),
        'analysis_timeframe': meta.get('analysis_timeframe'),
        'execution_timeframe': meta.get('execution_timeframe'),
        'confirmation_timeframe': meta.get('confirmation_timeframe'),
        'timeframe_selection_reason': meta.get('timeframe_selection_reason'),
        'decision': {
            'decision': decision.get('decision'),
            'score': decision.get('score'),
            'reasons': decision.get('reasons') if isinstance(decision.get('reasons'), list) else [],
        },
        'ai_decision': {
            'provider': ai_decision.get('provider'),
            'decision': ai_decision.get('decision'),
            'confidence': ai_decision.get('confidence'),
        },
        'auto_policy': {
            'state': auto_policy.get('state'),
            'block_new_entries': auto_policy.get('block_new_entries'),
            'reasons': auto_policy.get('reasons') if isinstance(auto_policy.get('reasons'), list) else [],
        },
        'performance_governor': {
            'suppressed': performance_governor.get('suppressed'),
            'reasons': performance_governor.get('reasons') if isinstance(performance_governor.get('reasons'), list) else [],
        },
        'ml_overlay': {
            'target_probability': ml_overlay.get('target_probability'),
            'fill_probability': ml_overlay.get('fill_probability'),
            'action': ml_overlay_action(ml_overlay),
            'reason': ml_overlay.get('reason'),
            'target_model_id': ml_overlay.get('target_model_id'),
            'fill_model_id': ml_overlay.get('fill_model_id'),
        },
        'geometry_optimizer': {
            'applied': geometry_optimizer.get('applied'),
            'phase': geometry_optimizer.get('phase'),
            'action': geometry_optimizer.get('action'),
            'notes': geometry_optimizer.get('notes') if isinstance(geometry_optimizer.get('notes'), list) else [],
            'original_sl': geometry_optimizer.get('original_sl'),
            'original_tp': geometry_optimizer.get('original_tp'),
            'suggested_timeframe': geometry_optimizer.get('suggested_timeframe'),
        },
        'ai_fast_path': {
            'applied': ai_fast_path.get('applied'),
            'final_decision': ai_fast_path.get('final_decision'),
            'pre_ai_decision': ai_fast_path.get('pre_ai_decision'),
            'reason': ai_fast_path.get('reason'),
            'triggers': ai_fast_path.get('triggers') if isinstance(ai_fast_path.get('triggers'), list) else [],
            'blocker_codes': ai_fast_path.get('blocker_codes') if isinstance(ai_fast_path.get('blocker_codes'), list) else [],
        },
    }
    return {key: value for key, value in compact.items() if value not in (None, {}, [])}
