from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from core.services.recalibration import get_recalibration_status, run_symbol_recalibration_batch
from core.services.symbol_adaptive import (
    build_symbol_plan_readonly,
    ensure_symbol_profiles,
    get_symbol_diagnostics,
    get_symbol_profile,
    list_symbol_profiles,
    train_symbol_profile,
    train_symbol_profiles_bulk,
    upsert_symbol_profile,
)
from core.storage.models import CandleCache, SymbolTrainingRun
from core.storage.repos import settings as settings_repo
from core.storage.session import get_db

router = APIRouter(dependencies=[Depends(verify_token)])


class SymbolProfilePatch(BaseModel):
    enabled: bool | None = None
    preferred_strategies: str | None = None
    decision_threshold_offset: int | None = None
    hold_bars_base: int | None = Field(default=None, ge=1, le=200)
    hold_bars_min: int | None = Field(default=None, ge=1, le=200)
    hold_bars_max: int | None = Field(default=None, ge=1, le=400)
    reentry_cooldown_sec: int | None = Field(default=None, ge=1, le=3600)
    risk_multiplier: float | None = Field(default=None, ge=0.1, le=3.0)
    aggressiveness: float | None = Field(default=None, ge=0.2, le=3.0)
    autotune: bool | None = None
    session_bias: str | None = None
    regime_bias: str | None = None
    preferred_side: str | None = None
    best_hours_json: list[int] | None = None
    blocked_hours_json: list[int] | None = None
    news_sensitivity: float | None = Field(default=None, ge=0.1, le=3.0)
    confidence_bias: float | None = Field(default=None, ge=0.1, le=3.0)
    notes: str | None = None


class SymbolTrainRequest(BaseModel):
    lookback_days: int = Field(default=180, ge=7, le=3650)
    timeframe: str = Field(default='1m')
    instrument_ids: list[str] | None = None


@router.get('')
async def list_profiles(db: Session = Depends(get_db)):
    return {'items': list_symbol_profiles(db)}


@router.get('/training-runs')
async def list_training_runs(limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(SymbolTrainingRun)
        .order_by(SymbolTrainingRun.ts.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return {
        'items': [
            {
                'id': row.id,
                'ts': int(row.ts),
                'instrument_id': row.instrument_id,
                'mode': row.mode,
                'status': row.status,
                'source': row.source,
                'candles_used': int(row.candles_used or 0),
                'trades_used': int(row.trades_used or 0),
                'recommendations': row.recommendations or {},
                'diagnostics': row.diagnostics or {},
                'notes': row.notes,
            }
            for row in rows
        ]
    }


@router.post('/train')
async def train_bulk(req: SymbolTrainRequest, db: Session = Depends(get_db)):
    instrument_ids = [item for item in (req.instrument_ids or []) if item]
    if not instrument_ids:
        raise HTTPException(status_code=400, detail='instrument_ids required')
    return train_symbol_profiles_bulk(db, instrument_ids, lookback_days=req.lookback_days, timeframe=req.timeframe, source='api_bulk')




@router.post('/ensure', summary='Seed/train symbol profiles for a set of instruments')
async def ensure_profiles(req: SymbolTrainRequest, db: Session = Depends(get_db)):
    instrument_ids = [item for item in (req.instrument_ids or []) if item]
    if not instrument_ids:
        raise HTTPException(status_code=400, detail='instrument_ids required')
    return ensure_symbol_profiles(db, instrument_ids, auto_train=True, lookback_days=req.lookback_days, timeframe=req.timeframe, source='api_ensure')


@router.get('/recalibration/status')
async def recalibration_status(db: Session = Depends(get_db)):
    return get_recalibration_status(db)


@router.post('/recalibration/run')
async def recalibration_run(force: bool = False, db: Session = Depends(get_db)):
    return run_symbol_recalibration_batch(db, force=force, source='api_manual')


@router.get('/{instrument_id:path}')
async def get_profile(instrument_id: str, db: Session = Depends(get_db)):
    profile = get_symbol_profile(instrument_id, db=db)
    if not profile:
        raise HTTPException(status_code=404, detail='Profile not found')
    settings = settings_repo.get_settings(db)
    candles = (
        db.query(CandleCache)
        .filter(CandleCache.instrument_id == instrument_id, CandleCache.timeframe == '1m')
        .order_by(CandleCache.ts.desc())
        .limit(80)
        .all()
    )
    history = [
        {'time': int(c.ts), 'open': float(c.open), 'high': float(c.high), 'low': float(c.low), 'close': float(c.close), 'volume': int(c.volume or 0)}
        for c in reversed(candles)
    ]
    plan = build_symbol_plan_readonly(db, instrument_id, history, settings).to_meta() if history else None
    diagnostics = get_symbol_diagnostics(db, instrument_id)
    return {'profile': profile, 'current_plan': plan, 'diagnostics': diagnostics}


@router.put('/{instrument_id:path}')
async def put_profile(instrument_id: str, patch: SymbolProfilePatch, db: Session = Depends(get_db)):
    return {'profile': upsert_symbol_profile(instrument_id, patch.model_dump(exclude_none=True), db=db)}


@router.post('/{instrument_id:path}/train')
async def train_profile(instrument_id: str, req: SymbolTrainRequest, db: Session = Depends(get_db)):
    return train_symbol_profile(db, instrument_id, lookback_days=req.lookback_days, timeframe=req.timeframe, source='api')


@router.get('/{instrument_id:path}/diagnostics')
async def diagnostics(instrument_id: str, lookback_days: int = 180, timeframe: str = '1m', db: Session = Depends(get_db)):
    return {'instrument_id': instrument_id, 'diagnostics': get_symbol_diagnostics(db, instrument_id, lookback_days=lookback_days, timeframe=timeframe)}
