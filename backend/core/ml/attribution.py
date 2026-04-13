from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

try:
    from sqlalchemy.orm import Session
except Exception:  # pragma: no cover
    Session = Any  # type: ignore

from core.storage.models import DecisionLog, Signal


_GUARDRAIL_LOG_TYPES = {
    'signal_risk_block',
    'execution_risk_block',
    'performance_governor_block',
    'auto_runtime_guard',
    'signal_freshness',
}


def _cutoff_ms(days: int) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=max(1, int(days or 1)))).timestamp() * 1000)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _signal_meta(signal: Any) -> dict[str, Any]:
    meta = getattr(signal, 'meta', None)
    return dict(meta or {}) if isinstance(meta, dict) else {}


def _extract_decision(meta: dict[str, Any]) -> dict[str, Any]:
    return dict(meta.get('decision') or {}) if isinstance(meta.get('decision'), dict) else {}


def _payload_dict(log: Any) -> dict[str, Any]:
    payload = getattr(log, 'payload', None)
    return dict(payload or {}) if isinstance(payload, dict) else {}


def _signal_strategy(meta: dict[str, Any]) -> str:
    multi = dict(meta.get('multi_strategy') or {}) if isinstance(meta.get('multi_strategy'), dict) else {}
    return str(multi.get('selected') or meta.get('strategy_name') or meta.get('strategy') or 'unknown')


def _signal_regime(meta: dict[str, Any]) -> str:
    adaptive = dict(meta.get('adaptive_plan') or {}) if isinstance(meta.get('adaptive_plan'), dict) else {}
    event = dict(meta.get('event_regime') or {}) if isinstance(meta.get('event_regime'), dict) else {}
    return str(event.get('regime') or adaptive.get('regime') or meta.get('regime') or 'unknown')


def _index_logs(decision_logs: Iterable[Any]) -> tuple[dict[str, list[Any]], int]:
    index: dict[str, list[Any]] = defaultdict(list)
    unmapped_guardrail_logs = 0
    for row in decision_logs:
        payload = _payload_dict(row)
        signal_id = str(payload.get('signal_id') or '')
        trace_id = str(payload.get('trace_id') or '')
        keys: list[str] = []
        if signal_id:
            keys.append(f's:{signal_id}')
        if trace_id:
            keys.append(f't:{trace_id}')
        if not keys and str(getattr(row, 'type', '') or '') in _GUARDRAIL_LOG_TYPES:
            unmapped_guardrail_logs += 1
        for key in keys:
            index[key].append(row)
    return index, unmapped_guardrail_logs


def _signal_logs(log_index: dict[str, list[Any]], *, signal_id: str, trace_id: str | None) -> list[Any]:
    rows: list[Any] = []
    seen: set[int] = set()
    keys = [f's:{signal_id}']
    if trace_id:
        keys.append(f't:{trace_id}')
    for key in keys:
        for row in log_index.get(key, []):
            row_key = id(row)
            if row_key in seen:
                continue
            seen.add(row_key)
            rows.append(row)
    rows.sort(key=lambda row: int(getattr(row, 'ts', 0) or 0))
    return rows


def _guardrail_reason(meta: dict[str, Any], logs: list[Any]) -> str | None:
    auto_policy = dict(meta.get('auto_policy') or {}) if isinstance(meta.get('auto_policy'), dict) else {}
    governor = dict(meta.get('performance_governor') or {}) if isinstance(meta.get('performance_governor'), dict) else {}
    freshness = dict(meta.get('signal_freshness') or {}) if isinstance(meta.get('signal_freshness'), dict) else {}
    if bool(auto_policy.get('block_new_entries')):
        return 'auto_policy'
    if bool(governor.get('suppressed')):
        return 'performance_governor'
    if bool(freshness.get('blocked')):
        return 'signal_freshness'
    for row in logs:
        log_type = str(getattr(row, 'type', '') or '')
        if log_type not in _GUARDRAIL_LOG_TYPES:
            continue
        if log_type in {'signal_risk_block', 'execution_risk_block'}:
            payload = _payload_dict(row)
            risk_reason = str(payload.get('risk_reason') or '').strip()
            return risk_reason or log_type
        return log_type
    return None


def _ml_veto_reason(meta: dict[str, Any]) -> str | None:
    overlay = dict(meta.get('ml_overlay') or {}) if isinstance(meta.get('ml_overlay'), dict) else {}
    suppress_take = bool(overlay.get('suppress_take'))
    reason = str(overlay.get('reason') or '')
    if suppress_take or reason == 'ml_take_veto':
        return reason or 'ml_take_veto'
    return None


def _filled_state(signal: Any, logs: list[Any]) -> bool:
    status = str(getattr(signal, 'status', '') or '').lower()
    if status == 'executed':
        return True
    return any(str(getattr(row, 'type', '') or '') == 'trade_filled' for row in logs)


def _closed_pnl_and_reason(logs: list[Any]) -> tuple[float | None, str | None]:
    close_logs = [row for row in logs if str(getattr(row, 'type', '') or '') == 'position_closed']
    if not close_logs:
        return None, None
    payload = _payload_dict(close_logs[-1])
    realized = _safe_float(payload.get('net_pnl'), _safe_float(payload.get('gross_pnl')))
    return realized, str(payload.get('reason') or '') or None


def build_ml_attribution_report_from_entities(
    signals: Iterable[Any],
    decision_logs: Iterable[Any],
    *,
    limit: int = 50,
) -> dict[str, Any]:
    signal_list = list(signals)
    log_index, unmapped_guardrail_logs = _index_logs(decision_logs)

    summary = Counter()
    ml_reason_breakdown = Counter()
    guardrail_reason_breakdown = Counter()
    close_reason_breakdown = Counter()
    recent_rows: list[dict[str, Any]] = []

    for signal in signal_list:
        signal_id = str(getattr(signal, 'id', '') or '')
        if not signal_id:
            continue
        meta = _signal_meta(signal)
        decision = _extract_decision(meta)
        trace_id = str(meta.get('trace_id') or '') or None
        logs = _signal_logs(log_index, signal_id=signal_id, trace_id=trace_id)
        pre_ml_decision = str(decision.get('decision') or '').upper()
        final_decision = str(meta.get('final_decision') or pre_ml_decision or 'UNKNOWN').upper()
        status = str(getattr(signal, 'status', '') or '')
        ml_reason = _ml_veto_reason(meta)
        guardrail_reason = _guardrail_reason(meta, logs)
        filled = _filled_state(signal, logs)
        realized_pnl, close_reason = _closed_pnl_and_reason(logs)

        summary['signal_generated'] += 1
        if pre_ml_decision == 'TAKE':
            summary['take_candidate'] += 1
        if final_decision == 'TAKE':
            summary['take_decided'] += 1
        if filled:
            summary['trade_filled'] += 1
        if realized_pnl is not None:
            if realized_pnl > 0:
                summary['trade_closed_profit'] += 1
            elif realized_pnl < 0:
                summary['trade_closed_loss'] += 1
            else:
                summary['trade_closed_flat'] += 1
        if guardrail_reason and realized_pnl is None and not filled:
            summary['take_blocked_by_guardrail'] += 1
            guardrail_reason_breakdown[guardrail_reason] += 1
        elif ml_reason and realized_pnl is None and not filled:
            summary['take_vetoed_by_ml'] += 1
            ml_reason_breakdown[ml_reason] += 1
        elif final_decision == 'TAKE' and realized_pnl is None and not filled:
            summary['take_not_filled'] += 1
        if close_reason:
            close_reason_breakdown[close_reason] += 1

        stage = 'filtered_before_take'
        if realized_pnl is not None:
            if realized_pnl > 0:
                stage = 'trade_closed_profit'
            elif realized_pnl < 0:
                stage = 'trade_closed_loss'
            else:
                stage = 'trade_closed_flat'
        elif filled:
            stage = 'trade_filled'
        elif guardrail_reason:
            stage = 'take_blocked_by_guardrail'
        elif ml_reason:
            stage = 'take_vetoed_by_ml'
        elif final_decision == 'TAKE':
            stage = 'take_not_filled'

        recent_rows.append({
            'signal_id': signal_id,
            'trace_id': trace_id,
            'instrument_id': str(getattr(signal, 'instrument_id', '') or 'unknown'),
            'created_ts': int(getattr(signal, 'created_ts', 0) or 0),
            'status': status,
            'strategy': _signal_strategy(meta),
            'regime': _signal_regime(meta),
            'pre_ml_decision': pre_ml_decision or None,
            'final_decision': final_decision,
            'stage': stage,
            'ml_reason': ml_reason,
            'guardrail_reason': guardrail_reason,
            'close_reason': close_reason,
            'realized_pnl': round(realized_pnl, 6) if realized_pnl is not None else None,
        })

    recent_rows.sort(key=lambda row: int(row.get('created_ts') or 0), reverse=True)
    limit = max(1, int(limit or 50))
    return {
        'summary': {
            'signal_generated': int(summary.get('signal_generated', 0)),
            'take_candidate': int(summary.get('take_candidate', 0)),
            'take_decided': int(summary.get('take_decided', 0)),
            'take_vetoed_by_ml': int(summary.get('take_vetoed_by_ml', 0)),
            'take_blocked_by_guardrail': int(summary.get('take_blocked_by_guardrail', 0)),
            'take_not_filled': int(summary.get('take_not_filled', 0)),
            'trade_filled': int(summary.get('trade_filled', 0)),
            'trade_closed_profit': int(summary.get('trade_closed_profit', 0)),
            'trade_closed_loss': int(summary.get('trade_closed_loss', 0)),
            'trade_closed_flat': int(summary.get('trade_closed_flat', 0)),
            'unmapped_guardrail_logs': int(unmapped_guardrail_logs),
        },
        'breakdowns': {
            'ml_reason': dict(ml_reason_breakdown),
            'guardrail_reason': dict(guardrail_reason_breakdown),
            'close_reason': dict(close_reason_breakdown),
        },
        'recent_rows': recent_rows[:limit],
    }


def build_ml_attribution_report(db: Session, *, days: int = 30, limit: int = 50) -> dict[str, Any]:
    days = max(1, min(int(days or 30), 180))
    cutoff = _cutoff_ms(days)
    signals = (
        db.query(Signal)
        .filter(Signal.created_ts >= cutoff)
        .order_by(Signal.created_ts.desc())
        .all()
    )
    decision_logs = (
        db.query(DecisionLog)
        .filter(DecisionLog.ts >= cutoff)
        .order_by(DecisionLog.ts.asc())
        .all()
    )
    payload = build_ml_attribution_report_from_entities(signals, decision_logs, limit=limit)
    payload['period_days'] = days
    payload['signals_scanned'] = len(signals)
    payload['decision_logs_scanned'] = len(decision_logs)
    payload['built_at_ts'] = int(datetime.now(timezone.utc).timestamp() * 1000)
    return payload
