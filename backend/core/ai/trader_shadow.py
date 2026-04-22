from __future__ import annotations

from apps.worker.ai.types import AIResult
from core.ai.agent_contracts import TraderAgentShadowDecision


def build_trader_agent_shadow(*, ai_result: AIResult, signal_id: str, instrument_id: str, final_decision: str) -> TraderAgentShadowDecision:
    return TraderAgentShadowDecision(
        signal_id=signal_id,
        instrument_id=instrument_id,
        action=str(ai_result.decision.value or '').lower(),
        confidence=int(ai_result.confidence or 0),
        provider=str(ai_result.provider or ''),
        reasoning=str(ai_result.reasoning or ''),
        final_decision=str(final_decision or ''),
        key_factors=list(ai_result.key_factors or []),
    )
