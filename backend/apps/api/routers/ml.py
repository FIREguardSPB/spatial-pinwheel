from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from core.ml.attribution import build_ml_attribution_report
from core.ml.dataset import build_training_datasets
from core.ml.runtime import build_ml_runtime_status, train_ml_models
from core.storage.repos.settings import get_settings
from core.storage.session import get_db

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get('/status')
async def get_ml_status(db: Session = Depends(get_db)):
    settings = get_settings(db)
    return build_ml_runtime_status(db, settings)


@router.get('/dataset')
async def get_ml_dataset(
    lookback_days: int = Query(120, ge=14, le=365),
    sample_limit: int = Query(50, ge=5, le=500),
    db: Session = Depends(get_db),
):
    datasets = build_training_datasets(db, lookback_days=lookback_days)
    return {
        'lookback_days': int(lookback_days),
        'datasets': {target: dataset.to_payload(limit=sample_limit) for target, dataset in datasets.items()},
    }




@router.get('/attribution')
async def get_ml_attribution(
    days: int = Query(30, ge=1, le=180),
    limit: int = Query(50, ge=5, le=500),
    db: Session = Depends(get_db),
):
    return build_ml_attribution_report(db, days=days, limit=limit)

@router.post('/train')
async def trigger_ml_training(
    force: bool = Query(True),
    source: str = Query('api_manual'),
    db: Session = Depends(get_db),
):
    settings = get_settings(db)
    return train_ml_models(db, settings, force=bool(force), source=source)
