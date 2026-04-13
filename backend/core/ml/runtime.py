from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from zoneinfo import ZoneInfo

try:
    from sqlalchemy.orm import Session
except Exception:  # pragma: no cover
    Session = Any  # type: ignore

from core.ml.dataset import build_live_feature_dict, build_training_datasets
from core.ml.registry import load_artifact, save_artifact
from core.ml.trainer import InsufficientTrainingDataError, TrainedModelArtifact, predict_probability, train_classifier
from core.storage.decision_log_utils import append_decision_log_best_effort
from core.storage.models import MLTrainingRun, Settings


MSK = ZoneInfo('Europe/Moscow')


@dataclass
class MLPredictionOverlay:
    enabled: bool
    model_ready: bool
    target_probability: float | None
    fill_probability: float | None
    risk_multiplier: float = 1.0
    threshold_adjustment: int = 0
    execution_priority: float = 1.0
    allocator_priority_multiplier: float = 1.0
    suppress_take: bool = False
    action: str = 'observe'
    reason: str = 'ml_disabled'
    target_model_id: str | None = None
    fill_model_id: str | None = None
    feature_summary: dict[str, Any] | None = None

    def to_meta(self) -> dict[str, Any]:
        payload = asdict(self)
        if isinstance(self.feature_summary, dict):
            payload['feature_summary'] = dict(self.feature_summary)
        return payload


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _get_setting(settings: Any, name: str, default: Any) -> Any:
    value = getattr(settings, name, None)
    return default if value is None else value


def _training_due(last_run_ts: int | None, *, interval_hours: int, hour_msk: int) -> bool:
    if not last_run_ts:
        return True
    now = datetime.now(timezone.utc)
    last_dt = datetime.fromtimestamp(int(last_run_ts) / 1000.0, tz=timezone.utc)
    if now - last_dt >= timedelta(hours=max(1, int(interval_hours or 24))):
        return True
    msk_now = now.astimezone(MSK)
    if int(msk_now.hour) == int(hour_msk or 4) and msk_now.date() > last_dt.astimezone(MSK).date():
        return True
    return False


def get_latest_training_run(db: Session, *, target: str, active_only: bool = True) -> MLTrainingRun | None:
    query = db.query(MLTrainingRun).filter(MLTrainingRun.target == target)
    if active_only:
        query = query.filter(MLTrainingRun.is_active == True)  # noqa: E712
    return query.order_by(MLTrainingRun.ts.desc()).first()


def list_training_runs(db: Session, *, limit: int = 20) -> list[MLTrainingRun]:
    return db.query(MLTrainingRun).order_by(MLTrainingRun.ts.desc()).limit(max(1, int(limit or 20))).all()


def _deactivate_other_runs(db: Session, *, target: str, keep_id: str) -> None:
    rows = db.query(MLTrainingRun).filter(MLTrainingRun.target == target, MLTrainingRun.id != keep_id, MLTrainingRun.is_active == True).all()  # noqa: E712
    for row in rows:
        row.is_active = False


def _record_training_run(
    db: Session,
    *,
    target: str,
    source: str,
    lookback_days: int,
    status: str,
    train_rows: int,
    validation_rows: int,
    artifact_path: str | None,
    model_type: str,
    feature_columns: list[str] | None,
    metrics: dict[str, Any] | None,
    params: dict[str, Any] | None,
    notes: str | None,
    activate: bool,
) -> MLTrainingRun:
    row = MLTrainingRun(
        id=f'ml_{uuid.uuid4().hex[:12]}',
        ts=_now_ms(),
        target=target,
        status=status,
        source=source,
        lookback_days=int(lookback_days or 0),
        train_rows=int(train_rows or 0),
        validation_rows=int(validation_rows or 0),
        artifact_path=artifact_path,
        model_type=model_type,
        feature_columns=feature_columns or [],
        metrics=metrics or {},
        params=params or {},
        notes=notes,
        is_active=bool(activate),
    )
    db.add(row)
    db.flush()
    if activate:
        _deactivate_other_runs(db, target=target, keep_id=row.id)
    return row


def train_ml_models(db: Session, settings: Settings, *, force: bool = False, source: str = 'manual_api') -> dict[str, Any]:
    enabled = bool(_get_setting(settings, 'ml_enabled', True))
    if not enabled and not force:
        return {'started': False, 'reason': 'ml_disabled'}

    lookback_days = int(_get_setting(settings, 'ml_lookback_days', 120) or 120)
    min_rows = int(_get_setting(settings, 'ml_min_training_samples', 80) or 80)
    datasets = build_training_datasets(db, lookback_days=lookback_days)
    results: list[dict[str, Any]] = []
    trained_any = False

    for target, dataset in datasets.items():
        try:
            artifact = train_classifier(dataset, min_rows=min_rows)
            run_id = f'ml_{uuid.uuid4().hex[:12]}'
            payload = {
                'target': artifact.target,
                'model_type': artifact.model_type,
                'vectorizer': artifact.vectorizer,
                'model': artifact.model,
                'feature_names': artifact.feature_names,
                'metrics': artifact.metrics,
                'params': artifact.params,
                'trained_at_ts': _now_ms(),
            }
            artifact_path = save_artifact(run_id, target, payload)
            row = _record_training_run(
                db,
                target=target,
                source=source,
                lookback_days=lookback_days,
                status='completed',
                train_rows=int(artifact.metrics.get('rows_train') or 0),
                validation_rows=int(artifact.metrics.get('rows_validation') or 0),
                artifact_path=artifact_path,
                model_type=artifact.model_type,
                feature_columns=list(artifact.feature_names),
                metrics=dict(artifact.metrics),
                params=dict(artifact.params),
                notes=f'trained from accumulated signals/trades over {lookback_days}d',
                activate=True,
            )
            trained_any = True
            append_decision_log_best_effort(
                log_type='ml_training_run',
                message=f'ML model trained for {target}',
                payload={'run_id': row.id, 'target': target, 'metrics': row.metrics, 'artifact_path': artifact_path, 'source': source},
            )
            results.append({
                'target': target,
                'run_id': row.id,
                'status': 'completed',
                'rows_total': len(dataset.rows),
                'metrics': row.metrics,
                'artifact_path': artifact_path,
            })
        except (InsufficientTrainingDataError, ValueError) as exc:
            row = _record_training_run(
                db,
                target=target,
                source=source,
                lookback_days=lookback_days,
                status='insufficient_data',
                train_rows=len(dataset.rows),
                validation_rows=0,
                artifact_path=None,
                model_type='logistic_regression',
                feature_columns=[],
                metrics={'rows_total': len(dataset.rows), 'label_balance': dataset.stats.get('labels')},
                params={'min_rows': min_rows},
                notes=str(exc),
                activate=False,
            )
            append_decision_log_best_effort(
                log_type='ml_training_run',
                message=f'ML training skipped for {target}: insufficient data',
                payload={'run_id': row.id, 'target': target, 'reason': str(exc), 'rows_total': len(dataset.rows), 'source': source},
            )
            results.append({'target': target, 'status': 'insufficient_data', 'reason': str(exc), 'rows_total': len(dataset.rows), 'run_id': row.id})

    db.commit()
    return {
        'started': trained_any,
        'lookback_days': lookback_days,
        'min_training_samples': min_rows,
        'datasets': {target: dataset.to_payload(limit=10) for target, dataset in datasets.items()},
        'results': results,
    }


def _overlay_action(reason: str | None, *, suppress_take: bool = False) -> str:
    if suppress_take or str(reason or '') == 'ml_take_veto':
        return 'veto'
    if str(reason or '') == 'ml_boost':
        return 'boost'
    if str(reason or '') == 'ml_risk_cut':
        return 'cut'
    if str(reason or '') in {'no_active_model', 'ml_disabled'}:
        return 'unavailable'
    return 'observe'


def build_ml_runtime_status(db: Session, settings: Settings) -> dict[str, Any]:
    latest_outcome = get_latest_training_run(db, target='trade_outcome', active_only=False)
    latest_fill = get_latest_training_run(db, target='take_fill', active_only=False)
    active_outcome = get_latest_training_run(db, target='trade_outcome', active_only=True)
    active_fill = get_latest_training_run(db, target='take_fill', active_only=True)
    runs = list_training_runs(db, limit=12)
    latest_training_ts = max(int(getattr(latest_outcome, 'ts', 0) or 0), int(getattr(latest_fill, 'ts', 0) or 0)) or None
    return {
        'enabled': bool(_get_setting(settings, 'ml_enabled', True)),
        'retrain_enabled': bool(_get_setting(settings, 'ml_retrain_enabled', True)),
        'lookback_days': int(_get_setting(settings, 'ml_lookback_days', 120) or 120),
        'min_training_samples': int(_get_setting(settings, 'ml_min_training_samples', 80) or 80),
        'retrain_interval_hours': int(_get_setting(settings, 'ml_retrain_interval_hours', 24) or 24),
        'retrain_hour_msk': int(_get_setting(settings, 'ml_retrain_hour_msk', 4) or 4),
        'allow_veto': bool(_get_setting(settings, 'ml_allow_take_veto', True)),
        'latest_training_ts': latest_training_ts,
        'active_models': {
            'trade_outcome': _run_payload(active_outcome),
            'take_fill': _run_payload(active_fill),
        },
        'recent_runs': [_run_payload(row) for row in runs],
    }


def _run_payload(row: MLTrainingRun | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        'id': row.id,
        'ts': int(row.ts or 0),
        'target': row.target,
        'status': row.status,
        'source': row.source,
        'lookback_days': int(row.lookback_days or 0),
        'train_rows': int(row.train_rows or 0),
        'validation_rows': int(row.validation_rows or 0),
        'artifact_path': row.artifact_path,
        'model_type': row.model_type,
        'metrics': row.metrics or {},
        'params': row.params or {},
        'notes': row.notes,
        'is_active': bool(row.is_active),
        'freshness_minutes': (round(max(0.0, (_now_ms() - int(row.ts or 0)) / 60000.0), 2) if int(row.ts or 0) > 0 else None),
        'freshness_hours': (round(max(0.0, (_now_ms() - int(row.ts or 0)) / 3600000.0), 3) if int(row.ts or 0) > 0 else None),
    }


def evaluate_ml_overlay(
    db: Session,
    settings: Settings,
    *,
    instrument_id: str,
    side: str,
    entry: float,
    sl: float,
    tp: float,
    size: float,
    ts_ms: int,
    meta: dict[str, Any] | None,
    final_decision: str,
) -> MLPredictionOverlay:
    if not bool(_get_setting(settings, 'ml_enabled', True)):
        return MLPredictionOverlay(enabled=False, model_ready=False, target_probability=None, fill_probability=None, action='unavailable', reason='ml_disabled')

    target_run = get_latest_training_run(db, target='trade_outcome', active_only=True)
    fill_run = get_latest_training_run(db, target='take_fill', active_only=True)
    target_artifact = load_artifact(getattr(target_run, 'artifact_path', None)) if target_run else None
    fill_artifact = load_artifact(getattr(fill_run, 'artifact_path', None)) if fill_run else None
    if target_artifact is None and fill_artifact is None:
        return MLPredictionOverlay(enabled=True, model_ready=False, target_probability=None, fill_probability=None, action='unavailable', reason='no_active_model')

    features = build_live_feature_dict(
        instrument_id=instrument_id,
        side=side,
        entry=entry,
        sl=sl,
        tp=tp,
        size=size,
        ts_ms=ts_ms,
        meta=meta,
        final_decision=final_decision,
    )
    target_probability = predict_probability(target_artifact, features) if target_artifact is not None else None
    fill_probability = predict_probability(fill_artifact, features) if fill_artifact is not None else None

    take_threshold = float(_get_setting(settings, 'ml_take_probability_threshold', 0.55) or 0.55)
    fill_threshold = float(_get_setting(settings, 'ml_fill_probability_threshold', 0.45) or 0.45)
    boost_threshold = float(_get_setting(settings, 'ml_risk_boost_threshold', 0.65) or 0.65)
    cut_threshold = float(_get_setting(settings, 'ml_risk_cut_threshold', 0.45) or 0.45)
    risk_mult = 1.0
    threshold_adjustment = 0
    execution_priority = 1.0
    allocator_priority_multiplier = 1.0
    suppress_take = False
    reason = 'neutral'
    action = 'observe'

    target_score = float(target_probability if target_probability is not None else 0.5)
    fill_score = float(fill_probability if fill_probability is not None else 0.5)
    allow_veto = bool(_get_setting(settings, 'ml_allow_take_veto', True))
    pass_risk = float(_get_setting(settings, 'ml_pass_risk_multiplier', 1.15) or 1.15)
    fail_risk = float(_get_setting(settings, 'ml_fail_risk_multiplier', 0.75) or 0.75)
    threshold_bonus = int(_get_setting(settings, 'ml_threshold_bonus', 4) or 4)
    threshold_penalty = int(_get_setting(settings, 'ml_threshold_penalty', 8) or 8)
    exec_boost = float(_get_setting(settings, 'ml_execution_priority_boost', 1.15) or 1.15)
    exec_penalty = float(_get_setting(settings, 'ml_execution_priority_penalty', 0.80) or 0.80)
    alloc_boost = float(_get_setting(settings, 'ml_allocator_boost', 1.10) or 1.10)
    alloc_penalty = float(_get_setting(settings, 'ml_allocator_penalty', 0.85) or 0.85)

    if final_decision == 'TAKE' and allow_veto and (target_probability is not None and target_score < take_threshold or fill_probability is not None and fill_score < fill_threshold):
        suppress_take = True
        risk_mult = fail_risk
        threshold_adjustment = threshold_penalty
        execution_priority = exec_penalty
        allocator_priority_multiplier = alloc_penalty
        reason = 'ml_take_veto'
        action = 'veto'
    elif target_probability is not None and target_score >= boost_threshold and (fill_probability is None or fill_score >= fill_threshold):
        risk_mult = pass_risk
        threshold_adjustment = -threshold_bonus
        execution_priority = exec_boost
        allocator_priority_multiplier = alloc_boost
        reason = 'ml_boost'
        action = 'boost'
    elif target_probability is not None and target_score < cut_threshold:
        risk_mult = fail_risk
        threshold_adjustment = threshold_penalty
        execution_priority = exec_penalty
        allocator_priority_multiplier = alloc_penalty
        reason = 'ml_risk_cut'
        action = 'cut'

    return MLPredictionOverlay(
        enabled=True,
        model_ready=True,
        target_probability=(round(target_probability, 4) if target_probability is not None else None),
        fill_probability=(round(fill_probability, 4) if fill_probability is not None else None),
        risk_multiplier=round(risk_mult, 4),
        threshold_adjustment=int(threshold_adjustment),
        execution_priority=round(execution_priority, 4),
        allocator_priority_multiplier=round(allocator_priority_multiplier, 4),
        suppress_take=bool(suppress_take),
        action=action,
        reason=reason,
        target_model_id=getattr(target_run, 'id', None),
        fill_model_id=getattr(fill_run, 'id', None),
        feature_summary={
            'instrument_id': instrument_id,
            'strategy': features.get('strategy'),
            'regime': features.get('regime'),
            'de_score': features.get('de_score'),
            'msk_hour': features.get('msk_hour'),
            'rr_multiple': features.get('rr_multiple'),
        },
    )


def maybe_run_scheduled_training(db: Session, settings: Settings, *, source: str = 'worker_schedule') -> dict[str, Any]:
    if not bool(_get_setting(settings, 'ml_enabled', True)):
        return {'started': False, 'reason': 'ml_disabled'}
    if not bool(_get_setting(settings, 'ml_retrain_enabled', True)):
        return {'started': False, 'reason': 'ml_retrain_disabled'}
    interval_hours = int(_get_setting(settings, 'ml_retrain_interval_hours', 24) or 24)
    hour_msk = int(_get_setting(settings, 'ml_retrain_hour_msk', 4) or 4)
    latest_run = get_latest_training_run(db, target='trade_outcome', active_only=False)
    last_ts = int(getattr(latest_run, 'ts', 0) or 0)
    if not _training_due(last_ts, interval_hours=interval_hours, hour_msk=hour_msk):
        return {'started': False, 'reason': 'not_due', 'latest_training_ts': last_ts or None}
    return train_ml_models(db, settings, force=False, source=source)
