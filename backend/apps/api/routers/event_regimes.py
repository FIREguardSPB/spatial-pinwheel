from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from core.storage.models import SymbolEventRegime
from core.storage.session import get_db

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get('')
async def list_event_regimes(
    instrument_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(SymbolEventRegime)
    if instrument_id:
        q = q.filter(SymbolEventRegime.instrument_id == instrument_id)
    rows = q.order_by(SymbolEventRegime.ts.desc()).limit(limit).all()
    return {
        'items': [
            {
                'id': row.id,
                'instrument_id': row.instrument_id,
                'ts': int(row.ts),
                'regime': row.regime,
                'severity': float(row.severity or 0.0),
                'direction': row.direction,
                'score_bias': int(row.score_bias or 0),
                'hold_bias': int(row.hold_bias or 0),
                'risk_bias': float(row.risk_bias or 1.0),
                'action': row.action,
                'payload': dict(row.payload or {}),
            }
            for row in rows
        ]
    }
