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
    trader_agent_shadow = meta.get('trader_agent_shadow') if isinstance(meta.get('trader_agent_shadow'), dict) else {}
    challenger_agent_shadow = meta.get('challenger_agent_shadow') if isinstance(meta.get('challenger_agent_shadow'), dict) else {}
    agent_merge_shadow = meta.get('agent_merge_shadow') if isinstance(meta.get('agent_merge_shadow'), dict) else {}
    ml_overlay = meta.get('ml_overlay') if isinstance(meta.get('ml_overlay'), dict) else {}
    geometry_optimizer = meta.get('geometry_optimizer') if isinstance(meta.get('geometry_optimizer'), dict) else {}
    ai_fast_path = meta.get('ai_fast_path') if isinstance(meta.get('ai_fast_path'), dict) else {}
    sector_filters = meta.get('sector_filters') if isinstance(meta.get('sector_filters'), dict) else {}
    cognitive_layer = meta.get('cognitive_layer') if isinstance(meta.get('cognitive_layer'), dict) else {}
    pre_persist_block = meta.get('pre_persist_block') if isinstance(meta.get('pre_persist_block'), dict) else {}
    candidate_snapshot = meta.get('candidate_snapshot') if isinstance(meta.get('candidate_snapshot'), dict) else {}

    compact: dict[str, Any] = {
        'final_decision': meta.get('final_decision'),
        'strategy_name': meta.get('strategy_name'),
        'strategy': meta.get('strategy'),
        'analysis_timeframe': meta.get('analysis_timeframe'),
        'context_timeframe': meta.get('context_timeframe'),
        'thesis_timeframe': meta.get('thesis_timeframe'),
        'execution_timeframe': meta.get('execution_timeframe'),
        'confirmation_timeframe': meta.get('confirmation_timeframe'),
        'market_regime_profile': meta.get('market_regime_profile'),
        'timeframe_selection_reason': meta.get('timeframe_selection_reason'),
        'timeframe_competition': meta.get('timeframe_competition') if isinstance(meta.get('timeframe_competition'), dict) else {},
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
        'trader_agent_shadow': {
            'action': trader_agent_shadow.get('action'),
            'confidence': trader_agent_shadow.get('confidence'),
            'provider': trader_agent_shadow.get('provider'),
            'final_decision': trader_agent_shadow.get('final_decision'),
        },
        'challenger_agent_shadow': {
            'stance': challenger_agent_shadow.get('stance'),
            'confidence': challenger_agent_shadow.get('confidence'),
            'recommended_adjustment': challenger_agent_shadow.get('recommended_adjustment'),
        },
        'agent_merge_shadow': {
            'consensus_action': agent_merge_shadow.get('consensus_action'),
            'challenger_stance': agent_merge_shadow.get('challenger_stance'),
        },
        'auto_policy': {
            'state': auto_policy.get('state'),
            'block_new_entries': auto_policy.get('block_new_entries'),
            'selective_throttle': auto_policy.get('selective_throttle'),
            'selective_min_score_buffer': auto_policy.get('selective_min_score_buffer'),
            'selective_min_rr': auto_policy.get('selective_min_rr'),
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
        'sector_filters': {
            'sector_id': sector_filters.get('sector_id'),
            'display_name': sector_filters.get('display_name'),
            'volatility_class': sector_filters.get('volatility_class'),
            'liquidity_class': sector_filters.get('liquidity_class'),
            'preferred_session': sector_filters.get('preferred_session'),
            'volume_filter_multiplier': sector_filters.get('volume_filter_multiplier'),
            'correlation_threshold': sector_filters.get('correlation_threshold'),
            'atr_stop_soft_min': sector_filters.get('atr_stop_soft_min'),
            'atr_stop_soft_max': sector_filters.get('atr_stop_soft_max'),
        },
        'ai_fast_path': {
            'applied': ai_fast_path.get('applied'),
            'final_decision': ai_fast_path.get('final_decision'),
            'pre_ai_decision': ai_fast_path.get('pre_ai_decision'),
            'reason': ai_fast_path.get('reason'),
            'triggers': ai_fast_path.get('triggers') if isinstance(ai_fast_path.get('triggers'), list) else [],
            'blocker_codes': ai_fast_path.get('blocker_codes') if isinstance(ai_fast_path.get('blocker_codes'), list) else [],
        },
        'pre_persist_block': {
            'code': pre_persist_block.get('code'),
            'reason': pre_persist_block.get('reason'),
            'stage': pre_persist_block.get('stage'),
            'ts': pre_persist_block.get('ts'),
        },
        'candidate_snapshot': {
            'strategy_name': candidate_snapshot.get('strategy_name'),
            'analysis_timeframe': candidate_snapshot.get('analysis_timeframe'),
            'context_timeframe': candidate_snapshot.get('context_timeframe'),
            'thesis_timeframe': candidate_snapshot.get('thesis_timeframe'),
            'execution_timeframe': candidate_snapshot.get('execution_timeframe'),
            'market_regime_profile': candidate_snapshot.get('market_regime_profile'),
            'stage': candidate_snapshot.get('stage'),
            'block_code': candidate_snapshot.get('block_code'),
            'block_reason': candidate_snapshot.get('block_reason'),
        },
        'cognitive_layer': {
            'status': cognitive_layer.get('status'),
            'final_decision': cognitive_layer.get('final_decision'),
            'strategy': cognitive_layer.get('strategy'),
            'regime': cognitive_layer.get('regime'),
            'operator_summary': cognitive_layer.get('operator_summary') if isinstance(cognitive_layer.get('operator_summary'), dict) else {},
            'contradictions': cognitive_layer.get('contradictions') if isinstance(cognitive_layer.get('contradictions'), list) else [],
        },
    }
    return {key: value for key, value in compact.items() if value not in (None, {}, [])}
