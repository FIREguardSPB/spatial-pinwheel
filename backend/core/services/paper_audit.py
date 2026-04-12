from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.storage.models import DecisionLog, Position, Signal


def _ts_days_ago(days: int) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)


def _date_key(ts_ms: int) -> str:
    return datetime.fromtimestamp(int(ts_ms) / 1000.0, tz=timezone.utc).strftime('%Y-%m-%d')


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _profit_factor(pnls: list[float]) -> float | None:
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    if not losses:
        return None if not wins else 999.0
    return round(sum(wins) / abs(sum(losses)), 4)


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def build_paper_audit(db: Session, *, days: int = 30) -> dict[str, Any]:
    cutoff = _ts_days_ago(days)
    positions = (
        db.query(Position)
        .filter(Position.qty == 0, Position.updated_ts >= cutoff)
        .order_by(Position.updated_ts.asc())
        .all()
    )
    logs = (
        db.query(DecisionLog)
        .filter(DecisionLog.ts >= cutoff)
        .order_by(DecisionLog.ts.asc())
        .all()
    )
    signals = db.query(Signal).filter(Signal.created_ts >= cutoff).all()
    signal_by_id = {str(s.id): s for s in signals}

    daily: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'date': '', 'pnl': 0.0, 'trades': 0, 'wins': 0, 'losses': 0,
        'tp': 0, 'sl': 0, 'time_decay': 0, 'late_failure': 0, 'execution_errors': 0,
    })
    exit_logs: dict[tuple[str, str], dict[str, Any]] = {}
    throttle_hits = 0
    throttle_multipliers: list[float] = []
    freshness_blocks = 0
    reallocation_count = 0
    recalibration_runs = 0
    exit_reason_counts = Counter()
    edge_decay_counts = Counter()
    close_quality_counts = Counter()
    hold_utils: list[float] = []
    tp_capture_ratios: list[float] = []
    rr_multiples: list[float] = []
    slippage_bps: list[float] = []
    mfe_pcts: list[float] = []
    mae_pcts: list[float] = []
    mfe_capture_ratios: list[float] = []
    mae_recovery_ratios: list[float] = []
    optimizer_adjustments = 0

    for log in logs:
        payload = dict(log.payload or {})
        if log.type == 'position_closed':
            key = (str(payload.get('instrument_id') or ''), str(payload.get('closed_order_id') or ''))
            exit_logs[key] = payload
            reason = str(payload.get('reason') or 'unknown')
            exit_reason_counts[reason] += 1
            diagnostics = dict(payload.get('exit_diagnostics') or {})
            decay = str(diagnostics.get('edge_decay_state') or 'unknown')
            qual = str(diagnostics.get('close_quality') or 'unknown')
            edge_decay_counts[decay] += 1
            close_quality_counts[qual] += 1
            if diagnostics.get('hold_utilization_pct') is not None:
                hold_utils.append(_safe_float(diagnostics.get('hold_utilization_pct')))
            if diagnostics.get('tp_capture_ratio') is not None:
                tp_capture_ratios.append(_safe_float(diagnostics.get('tp_capture_ratio')))
            if diagnostics.get('realized_rr_multiple') is not None:
                rr_multiples.append(_safe_float(diagnostics.get('realized_rr_multiple')))
            if diagnostics.get('slippage_to_requested_close_bps') is not None:
                slippage_bps.append(_safe_float(diagnostics.get('slippage_to_requested_close_bps')))
            if diagnostics.get('mfe_pct') is not None:
                mfe_pcts.append(_safe_float(diagnostics.get('mfe_pct')))
            if diagnostics.get('mae_pct') is not None:
                mae_pcts.append(_safe_float(diagnostics.get('mae_pct')))
            if diagnostics.get('realized_to_mfe_capture_ratio') is not None:
                mfe_capture_ratios.append(_safe_float(diagnostics.get('realized_to_mfe_capture_ratio')))
            if diagnostics.get('mae_recovery_ratio') is not None:
                mae_recovery_ratios.append(_safe_float(diagnostics.get('mae_recovery_ratio')))
        elif log.type == 'portfolio_optimizer_overlay':
            optimizer = dict(payload.get('optimizer') or {})
            mult = _safe_float(optimizer.get('optimizer_risk_multiplier'), 1.0)
            if abs(mult - 1.0) >= 0.01:
                optimizer_adjustments += 1
        elif log.type == 'pm_risk_throttle':
            throttle_hits += 1
            mult = _safe_float(payload.get('portfolio_risk_multiplier'), 0.0)
            if mult > 0:
                throttle_multipliers.append(mult)
        elif log.type == 'signal_freshness':
            fresh = dict(payload.get('freshness') or {})
            if bool(fresh.get('blocked')):
                freshness_blocks += 1
        elif log.type == 'capital_reallocation':
            reallocation_count += 1
        elif log.type == 'symbol_recalibration_batch':
            recalibration_runs += 1

    for pos in positions:
        date = _date_key(int(pos.updated_ts or pos.opened_ts or 0))
        row = daily[date]
        row['date'] = date
        pnl = _safe_float(pos.realized_pnl)
        row['pnl'] = round(_safe_float(row['pnl']) + pnl, 2)
        row['trades'] = int(row['trades']) + 1
        if pnl > 0:
            row['wins'] = int(row['wins']) + 1
        elif pnl < 0:
            row['losses'] = int(row['losses']) + 1
        signal = signal_by_id.get(str(getattr(pos, 'opened_signal_id', '') or ''))
        exit_payload = None
        if getattr(pos, 'closed_order_id', None):
            exit_payload = exit_logs.get((str(pos.instrument_id), str(pos.closed_order_id)))
        if exit_payload is None:
            for payload in exit_logs.values():
                if str(payload.get('signal_id') or '') == str(getattr(pos, 'opened_signal_id', '') or '') and str(payload.get('instrument_id') or '') == str(pos.instrument_id):
                    exit_payload = payload
                    break
        reason = str((exit_payload or {}).get('reason') or 'unknown').upper()
        diag = dict((exit_payload or {}).get('exit_diagnostics') or {})
        decay = str(diag.get('edge_decay_state') or '')
        if reason == 'TP':
            row['tp'] = int(row['tp']) + 1
        if reason == 'SL':
            row['sl'] = int(row['sl']) + 1
        if decay == 'time_decay':
            row['time_decay'] = int(row['time_decay']) + 1
        if decay == 'late_failure':
            row['late_failure'] = int(row['late_failure']) + 1
        meta = dict((signal.meta or {}) if signal else {})
        risk_sizing = dict(meta.get('risk_sizing') or {})
        if _safe_float(risk_sizing.get('portfolio_risk_multiplier'), 1.0) < 0.999:
            throttle_multipliers.append(_safe_float(risk_sizing.get('portfolio_risk_multiplier'), 1.0))

    error_signals = [s for s in signals if str(getattr(s, 'status', '')) == 'execution_error']
    for s in error_signals:
        date = _date_key(int(getattr(s, 'updated_ts', 0) or getattr(s, 'created_ts', 0) or 0))
        row = daily[date]
        row['date'] = date
        row['execution_errors'] = int(row['execution_errors']) + 1

    daily_rows: list[dict[str, Any]] = []
    total_day_pnls: list[float] = []
    green_days = 0
    red_days = 0
    for date in sorted(daily.keys()):
        row = daily[date]
        trades = int(row['trades'])
        wins = int(row['wins'])
        losses = int(row['losses'])
        pnl = round(_safe_float(row['pnl']), 2)
        total_day_pnls.append(pnl)
        if pnl > 0:
            green_days += 1
        elif pnl < 0:
            red_days += 1
        daily_rows.append({
            **row,
            'win_rate': round((wins / trades) * 100.0, 2) if trades else 0.0,
            'profit_factor': _profit_factor([p.realized_pnl for p in positions if _date_key(int(p.updated_ts or p.opened_ts or 0)) == date]),
        })

    total_closed = max(1, len(positions))
    time_decay_share = round((edge_decay_counts.get('time_decay', 0) / total_closed) * 100.0, 2)
    late_failure_share = round((edge_decay_counts.get('late_failure', 0) / total_closed) * 100.0, 2)
    fast_realization_share = round((edge_decay_counts.get('fast_realization', 0) / total_closed) * 100.0, 2)
    avg_throttle = _avg([v for v in throttle_multipliers if v > 0]) if throttle_multipliers else 1.0

    recommendations: list[str] = []
    if red_days > green_days and len(daily_rows) >= 5:
        recommendations.append('Красных дней больше, чем зелёных — усиливать PM throttle или снижать агрессию allocator.')
    if time_decay_share >= 25.0:
        recommendations.append('Слишком много выходов по time decay/session end — проверь hold bars и freshness penalty.')
    if late_failure_share >= 18.0:
        recommendations.append('Много late-failure выходов — вероятно, бот слишком долго держит слабую идею.')
    avg_tp_capture = _avg(tp_capture_ratios)
    if tp_capture_ratios and avg_tp_capture < 0.55:
        recommendations.append('Низкий TP capture ratio — прибыльные сделки закрываются слишком рано или геометрия TP слабая.')
    if avg_throttle > 0.95 and red_days >= 3:
        recommendations.append('PM throttle почти не срабатывает даже в плохие дни — стоит жёстче связать size с drawdown/loss streak.')
    if freshness_blocks >= 10:
        recommendations.append('Много stale blocks — проверь bootstrap latency, polling cadence и signal freshness settings.')
    avg_capture = _avg(mfe_capture_ratios)
    if mfe_capture_ratios and avg_capture < 0.45:
        recommendations.append('Низкий realized/MFE capture — бот недобирает уже достигнутую внутри сделки прибыль.')
    avg_mae = _avg(mae_pcts)
    if mae_pcts and avg_mae < -0.9:
        recommendations.append('Средний MAE слишком глубокий — вероятно, стопы или входы всё ещё слишком широкие для intraday режима.')

    return {
        'period_days': days,
        'summary': {
            'trading_days': len(daily_rows),
            'green_days': green_days,
            'red_days': red_days,
            'flat_days': max(0, len(daily_rows) - green_days - red_days),
            'avg_day_pnl': _avg(total_day_pnls),
            'best_day_pnl': round(max(total_day_pnls), 2) if total_day_pnls else 0.0,
            'worst_day_pnl': round(min(total_day_pnls), 2) if total_day_pnls else 0.0,
            'throttle_hits_count': throttle_hits,
            'avg_portfolio_risk_multiplier': round(avg_throttle, 4),
            'freshness_blocks_count': freshness_blocks,
            'capital_reallocations_count': reallocation_count,
            'portfolio_optimizer_adjustments_count': optimizer_adjustments,
            'recalibration_runs_count': recalibration_runs,
        },
        'exit_diagnostics': {
            'avg_hold_utilization_pct': _avg(hold_utils),
            'avg_tp_capture_ratio': avg_tp_capture,
            'avg_realized_rr_multiple': _avg(rr_multiples),
            'avg_adverse_slippage_bps': _avg(slippage_bps),
            'avg_mfe_pct': _avg(mfe_pcts),
            'avg_mae_pct': _avg(mae_pcts),
            'avg_mfe_capture_ratio': _avg(mfe_capture_ratios),
            'avg_mae_recovery_ratio': _avg(mae_recovery_ratios),
            'time_decay_exit_share_pct': time_decay_share,
            'late_failure_share_pct': late_failure_share,
            'fast_realization_share_pct': fast_realization_share,
            'close_quality_breakdown': dict(close_quality_counts),
            'exit_reason_breakdown': dict(exit_reason_counts),
            'edge_decay_breakdown': dict(edge_decay_counts),
        },
        'daily_rows': daily_rows,
        'recommendations': recommendations,
    }
