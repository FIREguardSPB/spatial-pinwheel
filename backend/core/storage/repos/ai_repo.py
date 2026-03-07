"""
P4-07: Repository for AI decision logging and statistics.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.worker.ai.types import AIResult, AIDecision
from core.storage.models import AIDecisionLog


def save_ai_decision(
    db: Session,
    signal_id: str,
    instrument_id: str,
    ai_result: AIResult,
    final_decision: str,
    de_score: int,
    prompt_text: str = "",
) -> AIDecisionLog:
    """Persist one AI decision record."""
    prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()[:16] if prompt_text else None

    record = AIDecisionLog(
        id=f"aid_{uuid.uuid4().hex[:12]}",
        ts=int(time.time() * 1000),
        signal_id=signal_id,
        instrument_id=instrument_id,
        provider=ai_result.provider,
        prompt_hash=prompt_hash,
        response_raw=(ai_result.raw_response or "")[:4000],
        ai_decision=ai_result.decision.value,
        ai_confidence=ai_result.confidence,
        ai_reasoning=ai_result.reasoning[:2000] if ai_result.reasoning else "",
        ai_key_factors=ai_result.key_factors or [],
        final_decision=final_decision,
        de_score=de_score,
        actual_outcome="pending",
        latency_ms=ai_result.latency_ms,
    )
    db.add(record)
    db.commit()
    return record


def update_outcome(db: Session, signal_id: str, outcome: str) -> None:
    """
    P4-07: Called by PositionMonitor after position close to record actual outcome.
    outcome: "profit" | "loss" | "stopped"
    """
    records = db.query(AIDecisionLog).filter(
        AIDecisionLog.signal_id == signal_id,
        AIDecisionLog.actual_outcome == "pending",
    ).all()
    for r in records:
        r.actual_outcome = outcome
    if records:
        db.commit()


def get_stats(db: Session) -> dict[str, Any]:
    """
    P4-07: Aggregate statistics for GET /api/v1/ai/stats.
    Returns win_rate per provider, avg_confidence, total_decisions.
    """
    total = db.query(func.count(AIDecisionLog.id)).scalar() or 0

    rows = db.query(
        AIDecisionLog.provider,
        func.count(AIDecisionLog.id).label("cnt"),
        func.avg(AIDecisionLog.ai_confidence).label("avg_conf"),
        func.sum(
            func.cast(AIDecisionLog.actual_outcome == "profit", int)
        ).label("wins"),
        func.sum(
            func.cast(AIDecisionLog.actual_outcome.in_(["profit", "loss", "stopped"]), int)
        ).label("closed"),
    ).group_by(AIDecisionLog.provider).all()

    providers = []
    for r in rows:
        closed = int(r.closed or 0)
        wins = int(r.wins or 0)
        providers.append({
            "provider": r.provider,
            "total": int(r.cnt),
            "avg_confidence": round(float(r.avg_conf or 0), 1),
            "win_rate": round(wins / closed * 100, 1) if closed > 0 else None,
            "closed_positions": closed,
        })

    return {"total_decisions": total, "providers": providers}


def list_decisions(
    db: Session,
    limit: int = 50,
    provider: str | None = None,
    outcome: str | None = None,
) -> list[AIDecisionLog]:
    q = db.query(AIDecisionLog)
    if provider:
        q = q.filter(AIDecisionLog.provider == provider)
    if outcome:
        q = q.filter(AIDecisionLog.actual_outcome == outcome)
    return q.order_by(AIDecisionLog.ts.desc()).limit(limit).all()


def export_jsonl(db: Session, limit: int = 1000) -> str:
    """
    P4-07: Export closed decisions as JSONL for fine-tuning.
    Format: {"prompt": "...", "completion": "...", "outcome": "..."}
    """
    from apps.worker.ai.prompts import SYSTEM_PROMPT
    records = (
        db.query(AIDecisionLog)
        .filter(AIDecisionLog.actual_outcome != "pending")
        .order_by(AIDecisionLog.ts.desc())
        .limit(limit)
        .all()
    )
    lines = []
    for r in records:
        entry = {
            "prompt": SYSTEM_PROMPT[:200] + "...",  # abbreviated
            "completion": json.dumps({
                "decision": r.ai_decision,
                "confidence": r.ai_confidence,
                "reasoning": r.ai_reasoning,
            }, ensure_ascii=False),
            "outcome": r.actual_outcome,
            "provider": r.provider,
            "instrument": r.instrument_id,
        }
        lines.append(json.dumps(entry, ensure_ascii=False))
    return "\n".join(lines)
