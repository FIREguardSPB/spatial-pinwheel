from __future__ import annotations

import csv
import io
import json
import time
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from core.services.business_metrics import build_metrics
from core.services.live_validation import build_live_trader_validation
from core.services.paper_audit import build_paper_audit
from core.services.trading_quality_audit import build_trading_quality_audit
from core.services.performance_layer import build_performance_layer
from core.services.performance_governor import build_performance_governor
from core.ml.runtime import build_ml_runtime_status
from core.services.symbol_adaptive import build_symbol_plan_readonly
from core.storage.models import CandleCache, DecisionLog, MLTrainingRun, Order, Position, Settings, Signal, SymbolEventRegime, SymbolProfile, SymbolTrainingRun, Trade, Watchlist
from core.storage.repos.settings import get_settings


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, 'model_dump'):
        return _json_safe(value.model_dump(mode='json'))
    return value



def _row_to_dict(row: Any, fields: list[str]) -> dict[str, Any]:
    return {field: _json_safe(getattr(row, field, None)) for field in fields}



def _rows_jsonl(rows: list[dict[str, Any]]) -> str:
    return ''.join(json.dumps(_json_safe(row), ensure_ascii=False) + '\n' for row in rows)



def _rows_csv(rows: list[dict[str, Any]], fieldnames: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _json_safe(row.get(key)) for key in fieldnames})
    return buf.getvalue()



def _recent_cutoff(days: int) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)



def _collect_recent_candles(db: Session, instrument_id: str, *, limit: int = 400) -> list[dict[str, Any]]:
    rows = (
        db.query(CandleCache)
        .filter(CandleCache.instrument_id == instrument_id, CandleCache.timeframe == '1m')
        .order_by(CandleCache.ts.desc())
        .limit(limit)
        .all()
    )
    result = [
        {
            'time': int(r.ts),
            'open': float(r.open or 0),
            'high': float(r.high or 0),
            'low': float(r.low or 0),
            'close': float(r.close or 0),
            'volume': int(r.volume or 0),
            'instrument_id': r.instrument_id,
            'broker_id': getattr(r, 'broker_id', None),
        }
        for r in reversed(rows)
    ]
    return result



def _instrument_candidates(db: Session, cutoff: int) -> list[str]:
    ids: list[str] = []
    ids.extend([str(x.instrument_id) for x in db.query(Watchlist).order_by(Watchlist.instrument_id.asc()).all()])
    ids.extend([str(x.instrument_id) for x in db.query(Signal.instrument_id).filter(Signal.created_ts >= cutoff).distinct().all()])
    ids.extend([str(x.instrument_id) for x in db.query(Trade.instrument_id).filter(Trade.ts >= cutoff).distinct().all()])
    seen: set[str] = set()
    ordered: list[str] = []
    for value in ids:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered[:60]



def build_forensic_export(db: Session, *, days: int = 30, instrument_id: str | None = None) -> tuple[bytes, dict[str, Any]]:
    cutoff = _recent_cutoff(days)
    settings = get_settings(db)

    signals = (
        db.query(Signal)
        .filter(Signal.created_ts >= cutoff)
        .order_by(Signal.created_ts.asc())
        .all()
    )
    trades = (
        db.query(Trade)
        .filter(Trade.ts >= cutoff)
        .order_by(Trade.ts.asc())
        .all()
    )
    orders = (
        db.query(Order)
        .filter(Order.created_ts >= cutoff)
        .order_by(Order.created_ts.asc())
        .all()
    )
    positions = db.query(Position).order_by(Position.instrument_id.asc()).all()
    logs = (
        db.query(DecisionLog)
        .filter(DecisionLog.ts >= cutoff)
        .order_by(DecisionLog.ts.asc())
        .all()
    )
    profiles = db.query(SymbolProfile).order_by(SymbolProfile.instrument_id.asc()).all()
    training_runs = (
        db.query(SymbolTrainingRun)
        .filter(SymbolTrainingRun.ts >= cutoff)
        .order_by(SymbolTrainingRun.ts.asc())
        .all()
    )
    event_regimes = (
        db.query(SymbolEventRegime)
        .filter(SymbolEventRegime.ts >= cutoff)
        .order_by(SymbolEventRegime.ts.asc())
        .all()
    )
    ml_runs = (
        db.query(MLTrainingRun)
        .filter(MLTrainingRun.ts >= cutoff)
        .order_by(MLTrainingRun.ts.asc())
        .all()
    )

    if instrument_id:
        signals = [row for row in signals if row.instrument_id == instrument_id]
        trades = [row for row in trades if row.instrument_id == instrument_id]
        orders = [row for row in orders if row.instrument_id == instrument_id]
        positions = [row for row in positions if row.instrument_id == instrument_id]
        logs = [row for row in logs if (row.payload or {}).get('instrument_id') == instrument_id or (row.payload or {}).get('signal_id') in {s.id for s in signals}]
        profiles = [row for row in profiles if row.instrument_id == instrument_id]
        training_runs = [row for row in training_runs if row.instrument_id == instrument_id]
        event_regimes = [row for row in event_regimes if row.instrument_id == instrument_id]
        ml_runs = list(ml_runs)

    summary = {
        'generated_ts': int(time.time() * 1000),
        'period_days': int(days),
        'instrument_id': instrument_id,
        'counts': {
            'signals': len(signals),
            'trades': len(trades),
            'orders': len(orders),
            'positions': len(positions),
            'decision_logs': len(logs),
            'profiles': len(profiles),
            'training_runs': len(training_runs),
            'event_regimes': len(event_regimes),
            'ml_training_runs': len(ml_runs),
        },
    }

    signal_rows = [_row_to_dict(row, ['id', 'instrument_id', 'broker_id', 'ts', 'side', 'entry', 'sl', 'tp', 'size', 'r', 'status', 'reason', 'meta', 'ai_influenced', 'ai_mode_used', 'ai_decision_id', 'created_ts', 'updated_ts']) for row in signals]
    trade_rows = [_row_to_dict(row, ['trade_id', 'instrument_id', 'broker_id', 'ts', 'side', 'price', 'qty', 'order_id', 'signal_id', 'strategy', 'trace_id']) for row in trades]
    order_rows = [_row_to_dict(row, ['order_id', 'instrument_id', 'broker_id', 'ts', 'side', 'type', 'price', 'qty', 'filled_qty', 'status', 'related_signal_id', 'strategy', 'trace_id', 'ai_influenced', 'ai_mode_used', 'created_ts', 'updated_ts']) for row in orders]
    position_rows = [_row_to_dict(row, ['instrument_id', 'broker_id', 'side', 'qty', 'opened_qty', 'avg_price', 'sl', 'tp', 'unrealized_pnl', 'realized_pnl', 'opened_signal_id', 'opened_order_id', 'closed_order_id', 'strategy', 'trace_id', 'entry_fee_est', 'exit_fee_est', 'total_fees_est', 'opened_ts', 'updated_ts']) for row in positions]
    log_rows = [_row_to_dict(row, ['id', 'ts', 'type', 'message', 'payload']) for row in logs]
    profile_rows = [_row_to_dict(row, ['instrument_id', 'enabled', 'preferred_strategies', 'decision_threshold_offset', 'hold_bars_base', 'hold_bars_min', 'hold_bars_max', 'reentry_cooldown_sec', 'risk_multiplier', 'aggressiveness', 'autotune', 'session_bias', 'regime_bias', 'preferred_side', 'best_hours_json', 'blocked_hours_json', 'news_sensitivity', 'confidence_bias', 'notes', 'source', 'profile_version', 'last_regime', 'last_strategy', 'last_threshold', 'last_hold_bars', 'last_win_rate', 'sample_size', 'last_tuned_ts', 'created_ts', 'updated_ts']) for row in profiles]
    training_rows = [_row_to_dict(row, ['id', 'ts', 'instrument_id', 'mode', 'status', 'source', 'candles_used', 'trades_used', 'recommendations', 'diagnostics', 'notes']) for row in training_runs]
    event_rows = [_row_to_dict(row, ['id', 'ts', 'instrument_id', 'regime', 'severity', 'direction', 'score_bias', 'hold_bias', 'risk_bias', 'action', 'payload']) for row in event_regimes]
    ml_run_rows = [_row_to_dict(row, ['id', 'ts', 'target', 'status', 'source', 'lookback_days', 'train_rows', 'validation_rows', 'artifact_path', 'model_type', 'feature_columns', 'metrics', 'params', 'notes', 'is_active']) for row in ml_runs]

    metrics = build_metrics(db, days=days)
    paper_audit = build_paper_audit(db, days=min(max(days, 3), 180))
    validation = build_live_trader_validation(db, days=min(max(days, 14), 365), weeks=min(max(max(2, days // 7), 2), 26))
    performance_layer = build_performance_layer(db, days=min(max(days, 14), 180))
    performance_governor = build_performance_governor(db, settings=settings, days=min(max(days, 14), 180))
    ml_runtime = build_ml_runtime_status(db, settings)

    effective_plans: list[dict[str, Any]] = []
    for candidate in ([instrument_id] if instrument_id else _instrument_candidates(db, cutoff)):
        if not candidate:
            continue
        candles = _collect_recent_candles(db, candidate)
        if len(candles) < 30:
            continue
        try:
            plan = build_symbol_plan_readonly(db, candidate, candles, settings)
            effective_plans.append({'instrument_id': candidate, 'plan': _json_safe(plan.to_meta())})
        except Exception as exc:
            effective_plans.append({'instrument_id': candidate, 'error': str(exc)})

    trace_links = []
    for row in signal_rows:
        meta = dict(row.get('meta') or {}) if isinstance(row.get('meta'), dict) else {}
        trace_id = meta.get('trace_id')
        if trace_id:
            trace_links.append({'signal_id': row['id'], 'trace_id': trace_id, 'instrument_id': row['instrument_id'], 'created_ts': row['created_ts']})

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('summary.json', json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))
        zf.writestr('settings.json', json.dumps(_json_safe(_row_to_dict(settings, [
            'id', 'risk_profile', 'risk_per_trade_pct', 'daily_loss_limit_pct', 'max_concurrent_positions', 'max_trades_per_day',
            'decision_threshold', 'strategy_name', 'trade_mode', 'bot_enabled', 'ai_mode', 'ai_primary_provider', 'ai_fallback_providers',
            'pm_risk_throttle_enabled', 'auto_degrade_enabled', 'auto_freeze_enabled', 'auto_policy_lookback_days',
            'auto_degrade_max_execution_errors', 'auto_freeze_max_execution_errors', 'auto_degrade_min_profit_factor', 'auto_freeze_min_profit_factor',
            'auto_degrade_min_expectancy', 'auto_freeze_min_expectancy', 'auto_degrade_drawdown_pct', 'auto_freeze_drawdown_pct',
            'auto_degrade_risk_multiplier', 'auto_degrade_threshold_penalty', 'auto_freeze_new_entries',
            'performance_governor_enabled', 'performance_governor_lookback_days', 'performance_governor_min_closed_trades',
            'performance_governor_strict_whitelist', 'performance_governor_auto_suppress', 'performance_governor_max_execution_error_rate',
            'performance_governor_min_take_fill_rate', 'performance_governor_pass_risk_multiplier', 'performance_governor_fail_risk_multiplier',
            'performance_governor_threshold_bonus', 'performance_governor_threshold_penalty', 'performance_governor_execution_priority_boost',
            'performance_governor_execution_priority_penalty', 'performance_governor_allocator_boost', 'performance_governor_allocator_penalty', 'updated_ts',
        ])), ensure_ascii=False, indent=2))
        zf.writestr('metrics.json', json.dumps(_json_safe(metrics), ensure_ascii=False, indent=2))
        zf.writestr('paper_audit.json', json.dumps(_json_safe(paper_audit), ensure_ascii=False, indent=2))
        zf.writestr('validation.json', json.dumps(_json_safe(validation), ensure_ascii=False, indent=2))
        zf.writestr('performance_layer.json', json.dumps(_json_safe(performance_layer), ensure_ascii=False, indent=2))
        zf.writestr('performance_governor.json', json.dumps(_json_safe(performance_governor), ensure_ascii=False, indent=2))
        zf.writestr('ml_runtime.json', json.dumps(_json_safe(ml_runtime), ensure_ascii=False, indent=2))
        zf.writestr('signals.jsonl', _rows_jsonl(signal_rows))
        zf.writestr('decision_log.jsonl', _rows_jsonl(log_rows))
        zf.writestr('traces.jsonl', _rows_jsonl(trace_links))
        zf.writestr('trades.csv', _rows_csv(trade_rows, ['trade_id', 'instrument_id', 'broker_id', 'ts', 'side', 'price', 'qty', 'order_id', 'signal_id', 'strategy', 'trace_id']))
        zf.writestr('orders.csv', _rows_csv(order_rows, ['order_id', 'instrument_id', 'broker_id', 'ts', 'side', 'type', 'price', 'qty', 'filled_qty', 'status', 'related_signal_id', 'strategy', 'trace_id', 'ai_influenced', 'ai_mode_used', 'created_ts', 'updated_ts']))
        zf.writestr('positions.json', json.dumps(_json_safe(position_rows), ensure_ascii=False, indent=2))
        zf.writestr('profiles.json', json.dumps(_json_safe(profile_rows), ensure_ascii=False, indent=2))
        zf.writestr('training_runs.json', json.dumps(_json_safe(training_rows), ensure_ascii=False, indent=2))
        zf.writestr('event_regimes.json', json.dumps(_json_safe(event_rows), ensure_ascii=False, indent=2))
        zf.writestr('ml_training_runs.json', json.dumps(_json_safe(ml_run_rows), ensure_ascii=False, indent=2))
        zf.writestr('effective_symbol_plans.json', json.dumps(_json_safe(effective_plans), ensure_ascii=False, indent=2))
    return buf.getvalue(), summary
