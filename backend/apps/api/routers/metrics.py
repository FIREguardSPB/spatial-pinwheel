from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from core.services.business_metrics import build_metrics
from core.storage.session import get_db

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("")
async def get_metrics(days: int = Query(7, ge=1, le=90), db: Session = Depends(get_db)):
    return build_metrics(db, days=days)
