from __future__ import annotations

from core.ai.agent_contracts import ChallengerAgentShadowDecision


def build_challenger_agent_shadow(*, signal_id: str, instrument_id: str, stance: str, confidence: int, main_objections: list[str] | None = None, recommended_adjustment: str = 'none') -> ChallengerAgentShadowDecision:
    return ChallengerAgentShadowDecision(
        signal_id=signal_id,
        instrument_id=instrument_id,
        stance=stance,
        confidence=int(confidence or 0),
        main_objections=list(main_objections or []),
        recommended_adjustment=recommended_adjustment,
    )
