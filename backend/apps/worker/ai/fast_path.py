from __future__ import annotations

from dataclasses import dataclass, field

from apps.worker.decision_engine.types import DecisionResult, Severity


@dataclass
class AIFastPathDecision:
    final_decision: str
    pre_ai_decision: str
    reason: str
    triggers: list[str] = field(default_factory=list)
    blocker_codes: list[str] = field(default_factory=list)
    applied: bool = True

    def to_meta(self) -> dict:
        return {
            'applied': self.applied,
            'final_decision': self.final_decision,
            'pre_ai_decision': self.pre_ai_decision,
            'reason': self.reason,
            'triggers': list(self.triggers),
            'blocker_codes': list(self.blocker_codes),
        }


def evaluate_ai_fast_path(
    *,
    evaluation: DecisionResult,
    final_decision: str,
    perf_governor: dict | None = None,
    freshness_meta: dict | None = None,
) -> AIFastPathDecision | None:
    """Return a deterministic AI skip decision when the signal is already non-viable.

    Rules are intentionally narrow:
    - any DE hard blockers
    - performance governor hard suppression
    - signal freshness hard block
    - final pre-AI decision is already REJECT

    Soft SKIP cases are not fast-pathed, so AI may still participate on survivors / gray zone setups.
    """
    perf_governor = perf_governor or {}
    freshness_meta = freshness_meta or {}

    blocker_codes = [
        str(reason.code.value)
        for reason in (evaluation.reasons or [])
        if getattr(reason, 'severity', None) == Severity.BLOCK
    ]

    triggers: list[str] = []
    notes: list[str] = []

    if blocker_codes:
        triggers.append('decision_engine_blockers')
        notes.append('DE hard blocks present')

    if bool(perf_governor.get('suppressed')):
        triggers.append('performance_governor_suppressed')
        reasons = perf_governor.get('reasons') or []
        if reasons:
            notes.append(f"performance governor suppressed: {'; '.join(str(r) for r in reasons[:3])}")
        else:
            notes.append('performance governor suppressed new entries')

    if bool(freshness_meta.get('blocked')):
        triggers.append('signal_freshness_blocked')
        notes.append(str(freshness_meta.get('reason') or 'signal freshness blocked'))

    normalized_final = str(final_decision or '').upper()
    if normalized_final == 'REJECT':
        triggers.append('final_reject_pre_ai')
        notes.append('final decision already REJECT before AI')

    if not triggers:
        return None

    deduped_notes = list(dict.fromkeys(note for note in notes if note))
    deduped_triggers = list(dict.fromkeys(triggers))
    deduped_codes = list(dict.fromkeys(code for code in blocker_codes if code))

    return AIFastPathDecision(
        final_decision=normalized_final or str(evaluation.decision.value),
        pre_ai_decision=str(evaluation.decision.value),
        reason='; '.join(deduped_notes) or 'deterministic pre-AI reject/skip',
        triggers=deduped_triggers,
        blocker_codes=deduped_codes,
    )
