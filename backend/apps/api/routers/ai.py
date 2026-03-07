"""
P4-07: AI advisor API endpoints.

GET  /api/v1/ai/stats   — win_rate по провайдерам, avg_confidence, total
GET  /api/v1/ai/log     — список AI-решений с фильтрами
GET  /api/v1/ai/export  — JSONL-экспорт для fine-tuning
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from core.storage.repos import ai_repo
from core.storage.session import get_db
from apps.api.deps import verify_token

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("/stats")
async def ai_stats(db: Session = Depends(get_db)):
    """Aggregate AI decision statistics by provider."""
    return ai_repo.get_stats(db)


@router.get("/log")
async def ai_log(
    limit: int = Query(50, ge=1, le=500),
    provider: str | None = Query(None),
    outcome: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """List AI decisions with optional filters."""
    records = ai_repo.list_decisions(db, limit=limit, provider=provider, outcome=outcome)
    return {
        "items": [
            {
                "id": r.id,
                "ts": r.ts,
                "signal_id": r.signal_id,
                "instrument_id": r.instrument_id,
                "provider": r.provider,
                "ai_decision": r.ai_decision,
                "ai_confidence": r.ai_confidence,
                "ai_reasoning": r.ai_reasoning,
                "key_factors": r.ai_key_factors or [],
                "final_decision": r.final_decision,
                "de_score": r.de_score,
                "actual_outcome": r.actual_outcome,
                "latency_ms": r.latency_ms,
            }
            for r in records
        ],
        "count": len(records),
    }


@router.get("/export", response_class=PlainTextResponse)
async def ai_export(
    limit: int = Query(1000, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    """Export closed AI decisions as JSONL for fine-tuning dataset."""
    jsonl = ai_repo.export_jsonl(db, limit=limit)
    return PlainTextResponse(
        content=jsonl,
        media_type="application/jsonl",
        headers={"Content-Disposition": "attachment; filename=ai_decisions.jsonl"},
    )
