from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TraderAgentShadowDecision:
    signal_id: str
    instrument_id: str
    action: str
    confidence: int
    provider: str
    reasoning: str
    final_decision: str
    key_factors: list[str] = field(default_factory=list)

    def to_meta(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChallengerAgentShadowDecision:
    signal_id: str
    instrument_id: str
    stance: str
    confidence: int
    main_objections: list[str] = field(default_factory=list)
    recommended_adjustment: str = 'none'

    def to_meta(self) -> dict[str, Any]:
        return asdict(self)
