from __future__ import annotations

from collections import Counter
import inspect
import threading
import time
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from apps.api.routers import account as account_router
from apps.api.routers import logs as logs_router
from apps.api.routers import settings as settings_router
from apps.api.routers import signals as signals_router
from apps.api.routers import trades as trades_router
from apps.api.routers import worker as worker_router
from core.services.ui_runtime import build_settings_runtime_snapshot
from core.services.degrade_policy import build_policy_runtime_payload_ui_safe
from core.storage.repos import settings as settings_repo
from core.storage.models import Signal
from core.storage.repos import signals as signals_repo
from core.storage.repos import state as state_repo
from core.storage.session import SessionLocal

router = APIRouter(dependencies=[Depends(verify_token)])

_UI_CACHE_LOCK = threading.Lock()
_UI_CACHE: dict[str, dict[str, Any]] = {}


def _cached_payload(key: str, ttl_sec: float, builder):
    now = time.monotonic()
    with _UI_CACHE_LOCK:
        cached = _UI_CACHE.get(key)
        if cached and float(cached.get('expires_at') or 0) > now:
            return cached['value']
    try:
        value = builder()
    except Exception:
        with _UI_CACHE_LOCK:
            cached = _UI_CACHE.get(key)
            if cached and cached.get('value') is not None:
                return cached['value']
        raise
    with _UI_CACHE_LOCK:
        _UI_CACHE[key] = {
            'expires_at': now + max(1.0, float(ttl_sec or 1.0)),
            'value': value,
        }
    return value

def _with_session(fn, *args, **kwargs):
    db = SessionLocal()
    try:
        params = list(inspect.signature(fn).parameters.values())
        if params and params[0].name == 'db':
            return fn(db, *args, **kwargs)
        if 'db' in inspect.signature(fn).parameters and 'db' not in kwargs:
            return fn(*args, db=db, **kwargs)
        return fn(*args, **kwargs)
    finally:
        db.close()


def _row_to_dict(row: Any) -> dict[str, Any]:
    if hasattr(row, '__table__'):
        return {column.name: getattr(row, column.name) for column in row.__table__.columns}
    return dict(row) if isinstance(row, dict) else {'value': row}


def _signals_summary(items: list[dict[str, Any]], *, total_count: int | None = None, latest_ts: int | None = None) -> dict[str, Any]:
    summary = Counter()
    for signal in items:
        summary['visible_count'] += 1
        if str(signal.get('final_decision') or '').upper() == 'TAKE':
            summary['take'] += 1
        if str(signal.get('ai_influence') or '') == 'affected decision':
            summary['ai_affected'] += 1
        meta = signal.get('meta') or {}
        auto_policy = meta.get('auto_policy') or {}
        governor = meta.get('performance_governor') or {}
        if bool(auto_policy.get('block_new_entries')) or bool(governor.get('suppressed')):
            summary['blocked_by_guardrail'] += 1
        if meta.get('ml_overlay'):
            summary['ml_seen'] += 1
    summary['total'] = int(total_count if total_count is not None else summary.get('visible_count', 0))
    summary['latest_signal_ts'] = latest_ts
    return dict(summary)


def _trades_summary(items: list[Any], *, total_count: int | None = None, latest_ts: int | None = None) -> dict[str, Any]:
    total_qty = 0.0
    instruments: set[str] = set()
    for trade in items:
        total_qty += float(getattr(trade, 'qty', 0) or 0)
        instrument_id = str(getattr(trade, 'instrument_id', '') or '')
        if instrument_id:
            instruments.add(instrument_id)
    return {
        'visible_count': len(items),
        'total': int(total_count if total_count is not None else len(items)),
        'total_qty': total_qty,
        'instruments': len(instruments),
        'latest_trade_ts': latest_ts,
    }


def _latest_candle_meta_sync(db: Session, instrument_id: str | None = None, timeframe: str = '1m') -> dict[str, Any]:
    if not instrument_id:
        row = db.query(settings_router.CandleCache.instrument_id, settings_router.CandleCache.ts).filter(settings_router.CandleCache.timeframe == timeframe).order_by(settings_router.CandleCache.ts.desc()).first()
        if not row:
            return {'latest_ts': None, 'instrument_id': None, 'timeframe': timeframe}
        return {'instrument_id': row[0], 'latest_ts': int(row[1]) if row[1] is not None else None, 'timeframe': timeframe}
    row = db.query(settings_router.CandleCache.ts).filter(settings_router.CandleCache.instrument_id == instrument_id, settings_router.CandleCache.timeframe == timeframe).order_by(settings_router.CandleCache.ts.desc()).first()
    return {'instrument_id': instrument_id, 'latest_ts': int(row[0]) if row and row[0] is not None else None, 'timeframe': timeframe}


def _count_signal_blocks_sync(db: Session) -> dict[str, int]:
    counts = Counter()
    rows = db.query(Signal.status).order_by(Signal.ts.desc()).limit(5000).all()
    for (status,) in rows:
        counts[str(status or 'unknown')] += 1
    return dict(counts)


def _runtime_bundle_sync(db: Session) -> dict[str, Any]:
    def _build() -> dict[str, Any]:
        snap = build_settings_runtime_snapshot(db)
        settings_payload = settings_router._settings_to_schema(snap['settings'])
        return {
            'settings_runtime': snap,
            'bot_status': snap['bot_status'],
            'settings': settings_payload.model_dump() if hasattr(settings_payload, 'model_dump') else settings_payload.dict(),
            'schedule': snap['schedule'],
            'watchlist': snap['watchlist'],
            'watchlist_sector_distribution': snap['watchlist_sector_distribution'],
            'ai_runtime': snap['ai_runtime'],
            'telegram': snap['telegram'],
            'auto_policy': snap['auto_policy'],
            'ml_runtime': snap['ml_runtime'],
            'pipeline_counters': snap['pipeline_counters'],
        }

    return _cached_payload('ui:runtime_bundle', 10.0, _build)


def _dashboard_payload_sync(db: Session, history_days: int, signals_limit: int, instrument_id: str | None = None, timeframe: str = '1m') -> dict[str, Any]:
    cache_key = f"ui:dashboard:{history_days}:{signals_limit}:{instrument_id or '*'}:{timeframe}"

    def _build() -> dict[str, Any]:
        account_summary = account_router.build_account_summary_sync(db)
        account_history = account_router.build_account_history_sync(db, history_days)
        runtime_payload = build_settings_runtime_snapshot(db)
        trades_payload = trades_router.build_trades_payload(db, limit=20, offset=0)
        trade_stats = trades_router.build_trade_stats_payload(db)
        orders_payload = {'items': [_row_to_dict(item) for item in state_repo.list_orders(db, active_only=True)], 'degraded': False, 'error': None}
        positions_payload = {'items': [_row_to_dict(item) for item in state_repo.list_positions(db)], 'degraded': False, 'error': None}
        signals_payload = signals_router.list_signals(limit=signals_limit, status=None, db=db, compact_meta=True)
        if instrument_id:
            signals_payload['items'] = [item for item in (signals_payload.get('items') or []) if item.get('instrument_id') == instrument_id]
        latest_candle = _latest_candle_meta_sync(db, instrument_id=instrument_id, timeframe=timeframe)
        return {
            'account_summary': account_summary,
            'account_history': account_history,
            'runtime': runtime_payload,
            'orders': orders_payload,
            'positions': positions_payload,
            'trades': trades_payload,
            'trade_stats': trade_stats,
            'signals': signals_payload,
            'signals_summary': _signals_summary(signals_payload.get('items') or [], total_count=signals_repo.count_signals(db), latest_ts=signals_repo.latest_signal_ts(db)),
            'latest_candle': latest_candle,
            'requested_instrument_id': instrument_id,
            'requested_timeframe': timeframe,
            'generated_ts': int(time.time() * 1000),
        }

    return _cached_payload(cache_key, 10.0, _build)



@router.get('/runtime/auto-policy-debug')
async def ui_runtime_auto_policy_debug():
    def _debug_payload(db: Session):
        settings_db = settings_repo.get_settings(db)
        return build_policy_runtime_payload_ui_safe(settings_db)
    return await run_in_threadpool(_with_session, _debug_payload)


@router.get('/runtime')
async def ui_runtime():
    runtime = await run_in_threadpool(_with_session, _runtime_bundle_sync)
    runtime['worker_status'] = await worker_router.get_worker_status()
    return runtime


@router.get('/dashboard')
async def ui_dashboard(
    instrument_id: str | None = Query(default=None),
    timeframe: str = Query(default='1m'),
    history_days: int = Query(default=7, ge=1, le=90),
    signals_limit: int = Query(default=40, ge=1, le=500),
):
    runtime = await run_in_threadpool(_with_session, _runtime_bundle_sync)
    runtime['worker_status'] = await worker_router.get_worker_status()
    payload = await run_in_threadpool(_with_session, _dashboard_payload_sync, history_days, signals_limit, instrument_id, timeframe)
    return {
        'runtime': runtime,
        **payload,
    }


@router.get('/settings')
async def ui_settings():
    runtime = await run_in_threadpool(_with_session, _runtime_bundle_sync)
    runtime['worker_status'] = await worker_router.get_worker_status()
    return {'runtime': runtime}


@router.get('/signals')
async def ui_signals(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    payload = await run_in_threadpool(_with_session, signals_router.list_signals, limit, status, compact_meta=True)
    total_count = await run_in_threadpool(_with_session, signals_repo.count_signals, status)
    latest_ts = await run_in_threadpool(_with_session, signals_repo.latest_signal_ts, status)
    status_counts = await run_in_threadpool(_with_session, _count_signal_blocks_sync)
    return {
        'items': payload.get('items') or [],
        'next_cursor': payload.get('next_cursor'),
        'summary': _signals_summary(payload.get('items') or [], total_count=total_count, latest_ts=latest_ts),
        'status_counts': status_counts,
    }


@router.get('/activity')
async def ui_activity(
    limit: int = Query(default=200, ge=1, le=1000),
):
    payload = await run_in_threadpool(_with_session, logs_router.get_logs, limit)
    return {
        'items': [_row_to_dict(item) for item in (payload.get('items') or [])],
        'next_cursor': payload.get('next_cursor'),
    }


@router.get('/trades')
async def ui_trades(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    payload = await run_in_threadpool(
        _with_session,
        trades_router.build_trades_payload,
        limit=limit,
        offset=offset,
    )
    items = payload.get('items') or []
    latest_ts = items[0].get('ts') if items else None
    return {
        **payload,
        'summary': _trades_summary(items, total_count=payload.get('total'), latest_ts=latest_ts),
    }


@router.get('/account')
async def ui_account(
    history_days: int = Query(default=30, ge=1, le=365),
):
    summary = await run_in_threadpool(_with_session, account_router.build_account_summary_sync)
    history = await run_in_threadpool(_with_session, account_router.build_account_history_sync, history_days)
    daily_stats = await run_in_threadpool(_with_session, account_router.build_daily_stats_sync)
    return {
        'summary': summary,
        'history': history,
        'daily_stats': daily_stats,
    }
