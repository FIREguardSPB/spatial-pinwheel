from __future__ import annotations

from typing import Any

from core.ai.agent_contracts import ChallengerAgentShadowDecision, TraderAgentShadowDecision


def merge_agent_shadows(trader: TraderAgentShadowDecision, challenger: ChallengerAgentShadowDecision) -> dict[str, Any]:
    consensus = trader.action
    if challenger.stance == 'challenge' and trader.action == 'take':
        consensus = 'review'
    return {
        'consensus_action': consensus,
        'trader_confidence': trader.confidence,
        'challenger_confidence': challenger.confidence,
        'challenger_stance': challenger.stance,
        'recommended_adjustment': challenger.recommended_adjustment,
        'main_objections': list(challenger.main_objections or []),
    }


def apply_agent_authority(*, current_decision: str, score: int, threshold: int, signal_meta: dict[str, Any], merged_shadow: dict[str, Any]) -> tuple[str, str]:
    decision = str(current_decision or '').upper()
    consensus = str((merged_shadow or {}).get('consensus_action') or '')
    selection_reason = str((signal_meta or {}).get('timeframe_selection_reason') or '')
    thesis_tf = str((signal_meta or {}).get('thesis_timeframe') or '')
    conviction = dict((signal_meta or {}).get('conviction_profile') or {})
    if decision in {'REJECT', 'SKIP'} and consensus == 'take' and thesis_tf in {'5m', '15m'} and selection_reason in {'requested', 'confirmation'} and bool(conviction.get('rescue_eligible')) and int(score or 0) >= max(int(threshold or 0) - 10, 0) and int((merged_shadow or {}).get('trader_confidence') or 0) >= 80 and str((merged_shadow or {}).get('challenger_stance') or '') == 'approve':
        return 'TAKE', 'agent_consensus_take'
    return decision, ''


def derive_agent_thesis_hints(*, signal_meta: dict[str, Any], merged_shadow: dict[str, Any]) -> dict[str, Any]:
    selection_reason = str((signal_meta or {}).get('timeframe_selection_reason') or '')
    thesis_tf = str((signal_meta or {}).get('thesis_timeframe') or '')
    conviction = dict((signal_meta or {}).get('conviction_profile') or {})
    consensus = str((merged_shadow or {}).get('consensus_action') or '')
    challenger_stance = str((merged_shadow or {}).get('challenger_stance') or '')
    trader_conf = int((merged_shadow or {}).get('trader_confidence') or 0)
    thesis_state = 'fragile'
    reentry_allowed = False
    winner_management_intent = 'neutral'
    if thesis_tf in {'5m', '15m'} and selection_reason in {'requested', 'confirmation'} and consensus == 'take' and challenger_stance == 'approve' and trader_conf >= 80:
        thesis_state = 'alive'
        reentry_allowed = bool(conviction.get('rescue_eligible'))
        winner_management_intent = 'preserve'
    return {
        'thesis_state': thesis_state,
        'reentry_allowed': reentry_allowed,
        'winner_management_intent': winner_management_intent,
    }


def should_defer_selective_throttle(*, signal_meta: dict[str, Any], score: int, threshold: int, rr_value: float) -> bool:
    meta = dict(signal_meta or {})
    conviction = dict(meta.get('conviction_profile') or {})
    return str(meta.get('thesis_timeframe') or '') in {'5m', '15m'} and str(meta.get('timeframe_selection_reason') or '') in {'requested', 'confirmation'} and str(conviction.get('tier') or 'C') in {'B', 'A', 'A+'} and bool(conviction.get('rescue_eligible')) and float(rr_value or 0.0) >= 1.3 and int(score or 0) >= max(int(threshold or 0) - 12, 0)


def apply_ai_first_decision(*, current_decision: str, merged_shadow: dict[str, Any], hard_blocked: bool) -> tuple[str, str]:
    if hard_blocked:
        return str(current_decision or '').upper(), ''
    if str((merged_shadow or {}).get('consensus_action') or '') == 'take' and str((merged_shadow or {}).get('challenger_stance') or '') == 'approve':
        return 'TAKE', 'ai_first_consensus_take'
    return str(current_decision or '').upper(), ''
