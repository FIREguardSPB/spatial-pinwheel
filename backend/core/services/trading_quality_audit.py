from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from sqlalchemy.orm import Session
except Exception:  # pragma: no cover
    Session = Any  # type: ignore

from core.storage.models import DecisionLog, Signal


@dataclass
class _Journey:
    signal_id: str
    instrument_id: str
    strategy: str
    status: str
    final_decision: str
    stage: str
    created_ts: int
    reason: str | None
    fills_count: int = 0
    closed_count: int = 0
    realized_pnl: float = 0.0
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'signal_id': self.signal_id,
            'instrument_id': self.instrument_id,
            'strategy': self.strategy,
            'status': self.status,
            'final_decision': self.final_decision,
            'stage': self.stage,
            'created_ts': self.created_ts,
            'reason': self.reason,
            'fills_count': self.fills_count,
            'closed_count': self.closed_count,
            'realized_pnl': round(self.realized_pnl, 4),
            'trace_id': self.trace_id,
        }


def _cutoff_ms(days: int) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _signal_strategy(signal: Signal | None) -> str:
    if not signal or not isinstance(signal.meta, dict):
        return 'unknown'
    meta = dict(signal.meta or {})
    multi = dict(meta.get('multi_strategy') or {})
    return str(multi.get('selected') or meta.get('strategy') or meta.get('strategy_name') or 'unknown')


def _signal_final_decision(signal: Signal | None) -> str:
    if not signal or not isinstance(signal.meta, dict):
        return 'UNKNOWN'
    meta = dict(signal.meta or {})
    decision = dict(meta.get('decision') or {})
    return str(meta.get('final_decision') or decision.get('decision') or 'UNKNOWN').upper()


def _signal_reason(signal: Signal | None) -> str | None:
    if not signal:
        return None
    meta = dict(signal.meta or {}) if isinstance(signal.meta, dict) else {}
    if isinstance(meta.get('execution_error'), dict):
        reason = meta['execution_error'].get('reason')
        if reason:
            return str(reason)
    for key in ('reason', 'merge_reason', 'event_merge_reason'):
        value = meta.get(key)
        if value:
            return str(value)
    signal_freshness = dict(meta.get('signal_freshness') or {}) if isinstance(meta, dict) else {}
    if signal_freshness.get('reason'):
        return str(signal_freshness.get('reason'))
    decision = dict(meta.get('decision') or {})
    reasons = decision.get('reasons') or []
    if isinstance(reasons, list) and reasons:
        first = reasons[0]
        if isinstance(first, dict):
            msg = first.get('message') or first.get('label') or first.get('code')
            if msg:
                return str(msg)
        if first:
            return str(first)
    return str(getattr(signal, 'reason', None) or '') or None


def _position_close_rating(diag: dict[str, Any]) -> str:
    grade = str(diag.get('exit_capture_grade') or '')
    if grade:
        return grade
    quality = str(diag.get('close_quality') or 'neutral')
    if quality in {'excellent', 'good'}:
        return 'good_capture'
    if quality in {'weak', 'poor'}:
        return 'poor_capture'
    return 'neutral_capture'


def _journey_stage(*, signal: Signal, fills_count: int, closed_count: int) -> str:
    status = str(getattr(signal, 'status', '') or '').lower()
    final_decision = _signal_final_decision(signal)
    if closed_count > 0:
        return 'closed'
    if fills_count > 0 or status == 'executed':
        return 'filled'
    if status == 'execution_error':
        return 'execution_error'
    if status == 'rejected' and final_decision == 'TAKE':
        return 'risk_rejected'
    if status == 'approved':
        return 'approved_waiting'
    if final_decision == 'TAKE':
        return 'take_not_filled'
    if status == 'pending_review':
        return 'pending_review'
    return 'filtered_out'


def build_trading_quality_audit(db: Session, *, days: int = 30) -> dict[str, Any]:
    days = max(3, min(int(days or 30), 180))
    cutoff = _cutoff_ms(days)

    signals = (
        db.query(Signal)
        .filter(Signal.created_ts >= cutoff)
        .order_by(Signal.created_ts.desc())
        .all()
    )
    logs = (
        db.query(DecisionLog)
        .filter(DecisionLog.ts >= cutoff)
        .order_by(DecisionLog.ts.desc())
        .all()
    )

    fills_by_signal: dict[str, list[dict[str, Any]]] = defaultdict(list)
    closes_by_signal: dict[str, list[dict[str, Any]]] = defaultdict(list)
    risk_blocks_by_signal: dict[str, list[str]] = defaultdict(list)
    execution_intents: set[str] = set()
    allocator_rows: list[dict[str, Any]] = []
    allocator_reason_counts = Counter()
    orphan_fills: list[dict[str, Any]] = []
    exit_rows: list[dict[str, Any]] = []

    for row in logs:
        payload = dict(row.payload or {})
        signal_id = str(payload.get('signal_id') or '')
        if row.type == 'trade_filled':
            entry = {
                'trade_id': payload.get('trade_id'),
                'order_id': payload.get('order_id'),
                'instrument_id': payload.get('instrument_id'),
                'ts': int(row.ts or 0),
                'qty': _safe_float(payload.get('qty')),
                'price': _safe_float(payload.get('price')),
                'trace_id': payload.get('trace_id'),
            }
            if signal_id:
                fills_by_signal[signal_id].append(entry)
            else:
                orphan_fills.append(entry)
        elif row.type == 'position_closed':
            diag = dict(payload.get('exit_diagnostics') or {})
            entry = {
                'instrument_id': payload.get('instrument_id'),
                'ts': int(row.ts or 0),
                'reason': payload.get('reason'),
                'net_pnl': _safe_float(payload.get('net_pnl')),
                'close_quality': diag.get('close_quality'),
                'exit_capture_grade': diag.get('exit_capture_grade'),
                'tp_capture_ratio': _safe_float(diag.get('tp_capture_ratio')) if diag.get('tp_capture_ratio') is not None else None,
                'mfe_capture_ratio': _safe_float(diag.get('realized_to_mfe_capture_ratio')) if diag.get('realized_to_mfe_capture_ratio') is not None else None,
                'missed_tp_value_rub': _safe_float(diag.get('missed_tp_value_rub')),
                'missed_mfe_value_rub': _safe_float(diag.get('missed_mfe_value_rub')),
                'edge_decay_state': diag.get('edge_decay_state'),
                'trace_id': payload.get('trace_id'),
            }
            exit_rows.append(entry)
            if signal_id:
                closes_by_signal[signal_id].append(entry)
        elif row.type in {'signal_risk_block', 'execution_risk_block'} and signal_id:
            risk_blocks_by_signal[signal_id].append(str(payload.get('risk_reason') or row.message or 'risk_block'))
        elif row.type == 'execution_intent' and signal_id:
            if str(payload.get('final_decision') or '').upper() == 'TAKE':
                execution_intents.add(signal_id)
        elif row.type == 'capital_reallocation':
            candidate = dict(payload.get('candidate') or {})
            result = dict(payload.get('result') or {})
            reason = str(candidate.get('rationale') or 'capital reallocation')
            if 'optimizer trim' in reason:
                allocator_reason_counts['optimizer_trim'] += 1
            elif candidate.get('current_notional_pct') and candidate.get('edge_improvement'):
                allocator_reason_counts['edge_upgrade'] += 1
            else:
                allocator_reason_counts['fallback'] += 1
            allocator_rows.append({
                'signal_id': signal_id or None,
                'trace_id': payload.get('trace_id'),
                'instrument_id': candidate.get('instrument_id'),
                'ts': int(row.ts or 0),
                'qty_ratio': _safe_float(candidate.get('qty_ratio')),
                'edge_improvement': _safe_float(candidate.get('edge_improvement')),
                'portfolio_pressure': _safe_float(candidate.get('portfolio_pressure')),
                'current_notional_pct': _safe_float(candidate.get('current_notional_pct')),
                'allocator_score': _safe_float(candidate.get('allocator_score')),
                'decay_bias': _safe_float(candidate.get('decay_bias')),
                'reason': reason,
                'result': result,
            })

    signals_count = len(signals)
    takes_count = 0
    approved_count = 0
    executed_signals_count = 0
    execution_error_count = 0
    risk_rejected_count = 0
    pending_count = 0
    filtered_out_count = 0
    closed_signals_count = 0
    funnel_counter = Counter()
    bottlenecks = Counter()
    strategy_rows: dict[str, dict[str, Any]] = defaultdict(lambda: {'strategy': 'unknown', 'signals': 0, 'takes': 0, 'filled': 0, 'closed': 0, 'pnl': 0.0, 'execution_errors': 0})
    instrument_rows: dict[str, dict[str, Any]] = defaultdict(lambda: {'instrument_id': 'unknown', 'signals': 0, 'takes': 0, 'filled': 0, 'closed': 0, 'pnl': 0.0, 'execution_errors': 0})
    journeys: list[_Journey] = []

    for signal in signals:
        signal_id = str(getattr(signal, 'id', '') or '')
        instrument_id = str(getattr(signal, 'instrument_id', '') or '')
        strategy = _signal_strategy(signal)
        final_decision = _signal_final_decision(signal)
        reason = _signal_reason(signal)
        fills = fills_by_signal.get(signal_id, [])
        closes = closes_by_signal.get(signal_id, [])
        status = str(getattr(signal, 'status', '') or '')
        stage = _journey_stage(signal=signal, fills_count=len(fills), closed_count=len(closes))
        realized_pnl = round(sum(_safe_float(item.get('net_pnl')) for item in closes), 4)
        journey = _Journey(
            signal_id=signal_id,
            instrument_id=instrument_id,
            strategy=strategy,
            status=status,
            final_decision=final_decision,
            stage=stage,
            created_ts=int(getattr(signal, 'created_ts', 0) or 0),
            reason=reason or (risk_blocks_by_signal.get(signal_id) or [None])[0],
            fills_count=len(fills),
            closed_count=len(closes),
            realized_pnl=realized_pnl,
            trace_id=(dict(signal.meta or {}) if isinstance(signal.meta, dict) else {}).get('trace_id'),
        )
        journeys.append(journey)
        funnel_counter[stage] += 1

        strategy_row = strategy_rows[strategy]
        strategy_row['strategy'] = strategy
        strategy_row['signals'] += 1
        instrument_row = instrument_rows[instrument_id]
        instrument_row['instrument_id'] = instrument_id
        instrument_row['signals'] += 1

        if final_decision == 'TAKE':
            takes_count += 1
            strategy_row['takes'] += 1
            instrument_row['takes'] += 1
        if status == 'approved':
            approved_count += 1
        if stage in {'filled', 'closed'}:
            executed_signals_count += 1
            strategy_row['filled'] += 1
            instrument_row['filled'] += 1
        if stage == 'closed':
            closed_signals_count += 1
            strategy_row['closed'] += 1
            instrument_row['closed'] += 1
            strategy_row['pnl'] += realized_pnl
            instrument_row['pnl'] += realized_pnl
        if stage == 'execution_error':
            execution_error_count += 1
            strategy_row['execution_errors'] += 1
            instrument_row['execution_errors'] += 1
        if stage == 'risk_rejected':
            risk_rejected_count += 1
        if stage == 'pending_review':
            pending_count += 1
        if stage == 'filtered_out':
            filtered_out_count += 1

        if stage in {'execution_error', 'risk_rejected', 'take_not_filled', 'pending_review'}:
            bottlenecks[f'{stage}:{journey.reason or "unknown"}'] += 1
        elif final_decision != 'TAKE':
            bottlenecks[f'decision_filter:{journey.reason or final_decision}'] += 1

    conversion_rate = round((executed_signals_count / signals_count) * 100.0, 2) if signals_count else 0.0
    take_fill_rate = round((executed_signals_count / takes_count) * 100.0, 2) if takes_count else 0.0
    close_rate = round((closed_signals_count / max(1, executed_signals_count)) * 100.0, 2) if executed_signals_count else 0.0

    allocator_count = len(allocator_rows)
    avg_realloc_ratio = round(sum(_safe_float(r.get('qty_ratio')) for r in allocator_rows) / allocator_count, 4) if allocator_count else 0.0
    avg_edge_improvement = round(sum(_safe_float(r.get('edge_improvement')) for r in allocator_rows) / allocator_count, 4) if allocator_count else 0.0
    avg_pressure = round(sum(_safe_float(r.get('portfolio_pressure')) for r in allocator_rows) / allocator_count, 4) if allocator_count else 0.0
    avg_allocator_score = round(sum(_safe_float(r.get('allocator_score')) for r in allocator_rows) / allocator_count, 4) if allocator_count else 0.0

    good_exits = 0
    weak_exits = 0
    avg_tp_capture = 0.0
    avg_mfe_capture = 0.0
    avg_missed_tp = 0.0
    avg_missed_mfe = 0.0
    time_decay_share = 0.0
    late_failure_share = 0.0
    if exit_rows:
        rated = [_position_close_rating({'exit_capture_grade': r.get('exit_capture_grade'), 'close_quality': r.get('close_quality')}) for r in exit_rows]
        good_exits = sum(1 for item in rated if item in {'excellent_capture', 'strong_capture', 'good_capture'})
        weak_exits = sum(1 for item in rated if item in {'weak_capture', 'poor_capture'})
        tp_values = [r['tp_capture_ratio'] for r in exit_rows if r.get('tp_capture_ratio') is not None]
        mfe_values = [r['mfe_capture_ratio'] for r in exit_rows if r.get('mfe_capture_ratio') is not None]
        avg_tp_capture = round(sum(tp_values) / len(tp_values), 4) if tp_values else 0.0
        avg_mfe_capture = round(sum(mfe_values) / len(mfe_values), 4) if mfe_values else 0.0
        avg_missed_tp = round(sum(_safe_float(r.get('missed_tp_value_rub')) for r in exit_rows) / len(exit_rows), 2)
        avg_missed_mfe = round(sum(_safe_float(r.get('missed_mfe_value_rub')) for r in exit_rows) / len(exit_rows), 2)
        time_decay_share = round((sum(1 for r in exit_rows if str(r.get('edge_decay_state') or '') == 'time_decay') / len(exit_rows)) * 100.0, 2)
        late_failure_share = round((sum(1 for r in exit_rows if str(r.get('edge_decay_state') or '') == 'late_failure') / len(exit_rows)) * 100.0, 2)

    summary_status = 'pass'
    if conversion_rate < 6.0 or take_fill_rate < 40.0 or execution_error_count >= max(4, signals_count // 8):
        summary_status = 'fail'
    elif conversion_rate < 12.0 or take_fill_rate < 60.0 or execution_error_count > 0:
        summary_status = 'partial'

    recommendations: list[str] = []
    if take_fill_rate < 65.0 and takes_count >= 5:
        recommendations.append('Низкая конверсия TAKE→fill: проверь path approved→paper/live execution и risk post-check после approval.')
    if execution_error_count > 0:
        recommendations.append('Есть execution_error: разберите unit-of-work и причины отказа исполнения по trace_id, пока это прямой удар по live readiness.')
    if allocator_count > 0 and avg_edge_improvement < 0.12:
        recommendations.append('Allocator делает перестановки с низким приростом edge — есть риск churn без реального улучшения портфеля.')
    if time_decay_share >= 20.0:
        recommendations.append('Слишком много time-decay выходов: бот передерживает идеи или слишком поздно принимает решение об exit.')
    if avg_mfe_capture and avg_mfe_capture < 0.45:
        recommendations.append('Низкий MFE capture: уже достигнутая внутри сделки прибыль плохо удерживается до выхода.')
    if avg_tp_capture and avg_tp_capture < 0.60:
        recommendations.append('Низкий TP capture: прибыльные идеи закрываются недостаточно эффективно.')

    bottleneck_rows = [
        {'bucket': key, 'count': count}
        for key, count in bottlenecks.most_common(10)
    ]
    allocator_rows_sorted = sorted(allocator_rows, key=lambda row: (row.get('allocator_score') or 0.0, row.get('edge_improvement') or 0.0), reverse=True)[:8]
    exit_rows_sorted = sorted(exit_rows, key=lambda row: (_safe_float(row.get('missed_mfe_value_rub')), _safe_float(row.get('missed_tp_value_rub'))), reverse=True)[:8]
    journey_rows = [item.to_dict() for item in sorted(journeys, key=lambda item: item.created_ts, reverse=True)[:40]]

    strategy_table = []
    for row in strategy_rows.values():
        row = dict(row)
        row['conversion_rate'] = round((row['filled'] / row['signals']) * 100.0, 2) if row['signals'] else 0.0
        row['take_fill_rate'] = round((row['filled'] / row['takes']) * 100.0, 2) if row['takes'] else 0.0
        row['closed_rate'] = round((row['closed'] / row['filled']) * 100.0, 2) if row['filled'] else 0.0
        row['pnl'] = round(_safe_float(row['pnl']), 4)
        strategy_table.append(row)
    strategy_table.sort(key=lambda row: (-row['signals'], row['strategy']))

    instrument_table = []
    for row in instrument_rows.values():
        row = dict(row)
        row['conversion_rate'] = round((row['filled'] / row['signals']) * 100.0, 2) if row['signals'] else 0.0
        row['take_fill_rate'] = round((row['filled'] / row['takes']) * 100.0, 2) if row['takes'] else 0.0
        row['closed_rate'] = round((row['closed'] / row['filled']) * 100.0, 2) if row['filled'] else 0.0
        row['pnl'] = round(_safe_float(row['pnl']), 4)
        instrument_table.append(row)
    instrument_table.sort(key=lambda row: (-row['signals'], row['instrument_id']))

    return {
        'period_days': days,
        'summary': {
            'status': summary_status,
            'signals_count': signals_count,
            'takes_count': takes_count,
            'approved_count': approved_count,
            'executed_signals_count': executed_signals_count,
            'closed_signals_count': closed_signals_count,
            'execution_error_count': execution_error_count,
            'risk_rejected_count': risk_rejected_count,
            'pending_count': pending_count,
            'filtered_out_count': filtered_out_count,
            'conversion_rate': conversion_rate,
            'take_fill_rate': take_fill_rate,
            'close_rate': close_rate,
            'orphan_fills_count': len(orphan_fills),
        },
        'funnel': [
            {
                'stage': stage,
                'count': count,
                'share_pct': round((count / signals_count) * 100.0, 2) if signals_count else 0.0,
            }
            for stage, count in [
                ('filtered_out', filtered_out_count),
                ('pending_review', pending_count),
                ('risk_rejected', risk_rejected_count),
                ('execution_error', execution_error_count),
                ('filled', executed_signals_count),
                ('closed', closed_signals_count),
            ]
        ],
        'allocator': {
            'status': 'pass' if allocator_count == 0 or avg_edge_improvement >= 0.18 else ('partial' if avg_edge_improvement >= 0.10 else 'fail'),
            'capital_reallocations_count': allocator_count,
            'avg_reallocation_ratio': avg_realloc_ratio,
            'avg_edge_improvement': avg_edge_improvement,
            'avg_portfolio_pressure': avg_pressure,
            'avg_allocator_score': avg_allocator_score,
            'reason_breakdown': dict(allocator_reason_counts),
            'recent_rows': allocator_rows_sorted,
        },
        'exit_capture': {
            'status': 'pass' if not exit_rows or (avg_mfe_capture >= 0.5 and time_decay_share < 18.0) else ('partial' if avg_mfe_capture >= 0.35 else 'fail'),
            'closed_trades_count': len(exit_rows),
            'excellent_or_good_share_pct': round((good_exits / len(exit_rows)) * 100.0, 2) if exit_rows else 0.0,
            'weak_or_poor_share_pct': round((weak_exits / len(exit_rows)) * 100.0, 2) if exit_rows else 0.0,
            'avg_tp_capture_ratio': avg_tp_capture,
            'avg_mfe_capture_ratio': avg_mfe_capture,
            'avg_missed_tp_value_rub': avg_missed_tp,
            'avg_missed_mfe_value_rub': avg_missed_mfe,
            'time_decay_share_pct': time_decay_share,
            'late_failure_share_pct': late_failure_share,
            'recent_rows': exit_rows_sorted,
        },
        'conversion_audit': {
            'status': summary_status,
            'bottlenecks': bottleneck_rows,
            'recent_signal_journeys': journey_rows,
            'strategy_rows': strategy_table[:10],
            'instrument_rows': instrument_table[:10],
            'orphan_fills': orphan_fills[:10],
        },
        'recommendations': recommendations,
    }
