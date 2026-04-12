from __future__ import annotations

import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

from sqlalchemy.orm import Session

from core.storage.models import DecisionLog, Position, SymbolProfile, SymbolTrainingRun, Watchlist
from core.storage.repos import settings as settings_repo
from core.services.symbol_adaptive import train_symbol_profile
from core.storage.decision_log_utils import append_decision_log_best_effort

_MSK = ZoneInfo('Europe/Moscow')


def _now_ms() -> int:
    return int(time.time() * 1000)


def _to_msk(ts_ms: int | None) -> datetime | None:
    if not ts_ms:
        return None
    return datetime.fromtimestamp(int(ts_ms) / 1000.0, tz=timezone.utc).astimezone(_MSK)


def _latest_recalibration_log(db: Session) -> DecisionLog | None:
    return (
        db.query(DecisionLog)
        .filter(DecisionLog.type == 'symbol_recalibration_batch')
        .order_by(DecisionLog.ts.desc())
        .first()
    )


def _recent_position_bias(db: Session, instrument_id: str) -> float:
    rows = (
        db.query(Position)
        .filter(Position.instrument_id == instrument_id, Position.qty == 0)
        .order_by(Position.updated_ts.desc())
        .limit(6)
        .all()
    )
    if not rows:
        return 0.0
    pnls = [float(r.realized_pnl or 0.0) for r in rows]
    avg = sum(pnls) / len(pnls)
    loss_bias = sum(1 for p in pnls if p <= 0) / len(pnls)
    return (8.0 if avg <= 0 else 0.0) + (loss_bias * 6.0)


def select_recalibration_candidates(db: Session, *, limit: int = 6) -> list[dict[str, Any]]:
    now_ms = _now_ms()
    rows = (
        db.query(Watchlist.instrument_id)
        .filter(Watchlist.is_active == True)  # noqa: E712
        .order_by(Watchlist.added_ts.asc())
        .all()
    )
    instrument_ids = [row[0] for row in rows if row and row[0]]
    items: list[dict[str, Any]] = []
    for instrument_id in instrument_ids:
        profile = db.query(SymbolProfile).filter(SymbolProfile.instrument_id == instrument_id).first()
        last_run = (
            db.query(SymbolTrainingRun)
            .filter(SymbolTrainingRun.instrument_id == instrument_id)
            .order_by(SymbolTrainingRun.ts.desc())
            .first()
        )
        last_ts = int((last_run.ts if last_run else None) or (getattr(profile, 'last_tuned_ts', 0) or 0) or 0)
        age_days = 999.0 if last_ts <= 0 else max(0.0, (now_ms - last_ts) / 86_400_000.0)
        sample_size = int(getattr(profile, 'sample_size', 0) or 0)
        recent_bias = _recent_position_bias(db, instrument_id)
        score = 0.0
        if last_ts <= 0:
            score += 60.0
        score += min(35.0, age_days * 4.0)
        if sample_size <= 0:
            score += 18.0
        elif sample_size < 6:
            score += 10.0
        score += recent_bias
        items.append({
            'instrument_id': instrument_id,
            'priority_score': round(score, 2),
            'last_training_ts': last_ts or None,
            'training_age_days': round(age_days, 2) if last_ts > 0 else None,
            'sample_size': sample_size,
            'recent_bias': round(recent_bias, 2),
        })
    items.sort(key=lambda item: (-float(item['priority_score']), str(item['instrument_id'])))
    return items[: max(1, limit)]


def get_recalibration_status(db: Session) -> dict[str, Any]:
    settings = settings_repo.get_settings(db)
    enabled = bool(getattr(settings, 'symbol_recalibration_enabled', True))
    hour_msk = int(getattr(settings, 'symbol_recalibration_hour_msk', 4) or 4)
    train_limit = max(1, int(getattr(settings, 'symbol_recalibration_train_limit', 6) or 6))
    lookback_days = max(30, int(getattr(settings, 'symbol_recalibration_lookback_days', 180) or 180))
    now_msk = datetime.now(timezone.utc).astimezone(_MSK)
    last_log = _latest_recalibration_log(db)
    last_msk = _to_msk(int(last_log.ts)) if last_log else None
    due = enabled and now_msk.hour >= hour_msk and (last_msk is None or last_msk.date() != now_msk.date())
    return {
        'enabled': enabled,
        'hour_msk': hour_msk,
        'train_limit': train_limit,
        'lookback_days': lookback_days,
        'now_msk': now_msk.isoformat(),
        'due': due,
        'last_batch': (
            {
                'ts': int(last_log.ts),
                'ts_msk': last_msk.isoformat() if last_msk else None,
                'payload': dict(last_log.payload or {}),
            }
            if last_log else None
        ),
        'candidates': select_recalibration_candidates(db, limit=train_limit),
    }


def run_symbol_recalibration_batch(db: Session, *, force: bool = False, source: str = 'manual') -> dict[str, Any]:
    status = get_recalibration_status(db)
    if not force and not status['due']:
        return {**status, 'started': False, 'reason': 'not_due'}

    candidates = list(status['candidates'])
    items: list[dict[str, Any]] = []
    completed = 0
    errors = 0
    for item in candidates:
        instrument_id = str(item['instrument_id'])
        try:
            result = train_symbol_profile(
                db,
                instrument_id,
                lookback_days=int(status['lookback_days']),
                timeframe='1m',
                source=source,
            )
            items.append({
                'instrument_id': instrument_id,
                'training_run_id': result.get('training_run_id'),
                'priority_score': item.get('priority_score'),
                'notes': (result.get('profile') or {}).get('notes'),
            })
            completed += 1
        except Exception as exc:
            errors += 1
            items.append({
                'instrument_id': instrument_id,
                'priority_score': item.get('priority_score'),
                'error': str(exc),
            })

    summary = {
        'source': source,
        'force': force,
        'completed': completed,
        'errors': errors,
        'train_limit': int(status['train_limit']),
        'lookback_days': int(status['lookback_days']),
        'candidate_count': len(candidates),
        'instrument_ids': [item.get('instrument_id') for item in items if item.get('instrument_id')],
    }
    db.commit()
    append_decision_log_best_effort(
        log_type='symbol_recalibration_batch',
        message=f"Symbol recalibration batch ({source}) completed={completed} errors={errors}",
        payload=summary,
        ts_ms=_now_ms(),
    )
    return {**get_recalibration_status(db), 'started': True, 'summary': summary, 'items': items}
