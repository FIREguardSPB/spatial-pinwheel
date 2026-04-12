from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from core.services.live_validation import (
    build_live_trader_validation,
    create_live_validation_snapshot,
    list_live_validation_snapshots,
)
from core.services.trading_quality_audit import build_trading_quality_audit
from core.services.performance_layer import build_performance_layer
from core.services.performance_governor import build_performance_governor
from core.storage.repos.settings import get_settings
from core.storage.session import get_db

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get('/live-checklist')
async def get_live_checklist(
    days: int = Query(45, ge=7, le=365),
    weeks: int = Query(8, ge=2, le=26),
    db: Session = Depends(get_db),
):
    return build_live_trader_validation(db, days=days, weeks=weeks)


@router.post('/snapshot')
async def create_snapshot(
    days: int = Query(45, ge=7, le=365),
    weeks: int = Query(8, ge=2, le=26),
    source: str = Query('api_manual'),
    db: Session = Depends(get_db),
):
    return create_live_validation_snapshot(db, days=days, weeks=weeks, source=source)


@router.get('/snapshots')
async def get_snapshots(limit: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)):
    return {'items': list_live_validation_snapshots(db, limit=limit)}


@router.get('/trading-quality')
async def get_trading_quality(
    days: int = Query(30, ge=3, le=180),
    db: Session = Depends(get_db),
):
    return build_trading_quality_audit(db, days=days)


@router.get('/performance-layer')
async def get_performance_layer(
    days: int = Query(45, ge=7, le=180),
    timeframe: str = Query('1m'),
    history_limit: int = Query(720, ge=320, le=3000),
    folds: int = Query(4, ge=2, le=8),
    max_instruments: int = Query(8, ge=1, le=16),
    db: Session = Depends(get_db),
):
    return build_performance_layer(
        db,
        days=days,
        timeframe=timeframe,
        history_limit=history_limit,
        folds=folds,
        max_instruments=max_instruments,
    )


@router.get('/performance-governor')
async def get_performance_governor_view(
    days: int = Query(45, ge=7, le=180),
    db: Session = Depends(get_db),
):
    settings = get_settings(db)
    return build_performance_governor(db, settings=settings, days=days)
