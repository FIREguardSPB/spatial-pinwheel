from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

try:
    from sqlalchemy.orm import Session
except Exception:  # pragma: no cover
    Session = Any  # type: ignore

from core.storage.models import AIDecisionLog, DecisionLog, Position, Signal


@dataclass
class TrainingRow:
    signal_id: str
    instrument_id: str
    target: str
    label: int
    features: dict[str, Any]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            'signal_id': self.signal_id,
            'instrument_id': self.instrument_id,
            'target': self.target,
            'label': int(self.label),
            'features': dict(self.features),
            'meta': dict(self.meta),
        }


@dataclass
class TrainingDataset:
    target: str
    rows: list[TrainingRow]
    lookback_days: int
    stats: dict[str, Any]

    def to_payload(self, *, limit: int = 200) -> dict[str, Any]:
        label_counts = Counter(int(row.label) for row in self.rows)
        return {
            'target': self.target,
            'lookback_days': self.lookback_days,
            'rows_count': len(self.rows),
            'label_counts': dict(label_counts),
            'stats': dict(self.stats),
            'sample_rows': [row.to_dict() for row in self.rows[: max(1, int(limit))]],
        }


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _cutoff_ms(days: int) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=max(1, int(days or 1)))).timestamp() * 1000)


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


def _signal_meta(signal: Signal | None) -> dict[str, Any]:
    if signal is None or not isinstance(getattr(signal, 'meta', None), dict):
        return {}
    return dict(signal.meta or {})


def _extract_strategy(meta: dict[str, Any]) -> str:
    multi = dict(meta.get('multi_strategy') or {}) if isinstance(meta.get('multi_strategy'), dict) else {}
    return str(multi.get('selected') or meta.get('strategy_name') or meta.get('strategy') or 'unknown')


def _extract_regime(meta: dict[str, Any]) -> str:
    adaptive = dict(meta.get('adaptive_plan') or {}) if isinstance(meta.get('adaptive_plan'), dict) else {}
    event = dict(meta.get('event_regime') or {}) if isinstance(meta.get('event_regime'), dict) else {}
    return str(event.get('regime') or adaptive.get('regime') or meta.get('regime') or meta.get('market_regime') or 'unknown')


def _extract_ai_decision(meta: dict[str, Any]) -> dict[str, Any]:
    if isinstance(meta.get('ai_decision'), dict):
        return dict(meta.get('ai_decision') or {})
    return {}


def _extract_decision(meta: dict[str, Any]) -> dict[str, Any]:
    if isinstance(meta.get('decision'), dict):
        return dict(meta.get('decision') or {})
    return {}


def _r_multiple(entry: float, sl: float, tp: float) -> float:
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk <= 0:
        return 0.0
    return reward / risk


def _msk_hour(ts_ms: int) -> int:
    try:
        dt = datetime.fromtimestamp(int(ts_ms) / 1000.0, tz=timezone.utc) + timedelta(hours=3)
        return int(dt.hour)
    except Exception:
        return 0


def build_feature_dict_from_signal(signal: Signal | None, *, signal_meta: dict[str, Any] | None = None, final_decision: str | None = None, ai_row: Any | None = None) -> dict[str, Any]:
    meta = signal_meta if signal_meta is not None else _signal_meta(signal)
    decision = _extract_decision(meta)
    ai_meta = _extract_ai_decision(meta)
    adaptive = dict(meta.get('adaptive_plan') or {}) if isinstance(meta.get('adaptive_plan'), dict) else {}
    event = dict(meta.get('event_regime') or {}) if isinstance(meta.get('event_regime'), dict) else {}
    freshness = dict(meta.get('signal_freshness') or {}) if isinstance(meta.get('signal_freshness'), dict) else {}
    economics = dict(meta.get('economic_summary') or meta.get('economics') or {}) if isinstance(meta.get('economic_summary') or meta.get('economics'), dict) else {}
    optimizer = dict(meta.get('portfolio_optimizer') or {}) if isinstance(meta.get('portfolio_optimizer'), dict) else {}
    governor = dict(meta.get('performance_governor') or {}) if isinstance(meta.get('performance_governor'), dict) else {}
    auto_policy = dict(meta.get('auto_policy') or {}) if isinstance(meta.get('auto_policy'), dict) else {}
    geometry = dict(meta.get('geometry_optimizer') or {}) if isinstance(meta.get('geometry_optimizer'), dict) else {}
    multi_tf = dict(meta.get('multi_timeframe') or {}) if isinstance(meta.get('multi_timeframe'), dict) else {}

    entry = _safe_float(getattr(signal, 'entry', None) if signal is not None else meta.get('entry'))
    sl = _safe_float(getattr(signal, 'sl', None) if signal is not None else meta.get('sl'))
    tp = _safe_float(getattr(signal, 'tp', None) if signal is not None else meta.get('tp'))
    size = _safe_float(getattr(signal, 'size', None) if signal is not None else meta.get('size'))
    ts = _safe_int(getattr(signal, 'created_ts', None) if signal is not None else meta.get('ts'))
    status = str(getattr(signal, 'status', None) if signal is not None else meta.get('status') or '')
    side = str(getattr(signal, 'side', None) if signal is not None else meta.get('side') or 'UNKNOWN')
    instrument_id = str(getattr(signal, 'instrument_id', None) if signal is not None else meta.get('instrument_id') or 'unknown')
    strategy = _extract_strategy(meta)
    regime = _extract_regime(meta)
    ai_confidence = _safe_float(ai_meta.get('confidence'))
    ai_provider = str(ai_meta.get('provider') or (getattr(ai_row, 'provider', None) if ai_row is not None else '') or 'none')
    ai_decision = str(ai_meta.get('decision') or (getattr(ai_row, 'ai_decision', None) if ai_row is not None else '') or 'NONE')
    final_decision = str(final_decision or meta.get('final_decision') or decision.get('decision') or 'UNKNOWN').upper()
    de_score = _safe_float(decision.get('score') or meta.get('event_adjusted_score'))
    sl_distance_pct = abs(entry - sl) / entry * 100.0 if entry > 0 else 0.0
    tp_distance_pct = abs(tp - entry) / entry * 100.0 if entry > 0 else 0.0

    return {
        'instrument_id': instrument_id,
        'side': side,
        'strategy': strategy,
        'regime': regime,
        'analysis_timeframe': str(meta.get('analysis_timeframe') or adaptive.get('analysis_timeframe') or multi_tf.get('selected_timeframe') or '1m'),
        'execution_timeframe': str(meta.get('execution_timeframe') or adaptive.get('execution_timeframe') or '1m'),
        'confirmation_timeframe': str(meta.get('confirmation_timeframe') or adaptive.get('confirmation_timeframe') or '15m'),
        'status': status,
        'final_decision': final_decision,
        'msk_hour': _msk_hour(ts),
        'entry_price': round(entry, 6),
        'position_size': round(size, 6),
        'sl_distance_pct': round(sl_distance_pct, 6),
        'tp_distance_pct': round(tp_distance_pct, 6),
        'rr_multiple': round(_r_multiple(entry, sl, tp), 6),
        'de_score': round(de_score, 4),
        'ai_confidence': round(ai_confidence, 4),
        'ai_provider': ai_provider,
        'ai_decision': ai_decision,
        'event_severity': round(_safe_float(event.get('severity')), 6),
        'event_score_bias': round(_safe_float(event.get('score_bias')), 4),
        'event_risk_bias': round(_safe_float(event.get('risk_bias'), 1.0), 6),
        'adaptive_risk_multiplier': round(_safe_float(adaptive.get('risk_multiplier'), 1.0), 6),
        'adaptive_threshold': _safe_int(adaptive.get('decision_threshold')),
        'freshness_penalty': round(_safe_float(freshness.get('penalty_score')), 4),
        'bars_since_signal': round(_safe_float(freshness.get('bars_since_signal')), 4),
        'economic_valid': 1 if economics.get('economic_filter_valid') else 0,
        'commission_dominance_ratio': round(_safe_float(economics.get('commission_dominance_ratio')), 6),
        'breakeven_move_pct': round(_safe_float(economics.get('breakeven_move_pct')), 6),
        'optimizer_risk_multiplier': round(_safe_float(optimizer.get('optimizer_risk_multiplier'), 1.0), 6),
        'governor_risk_multiplier': round(_safe_float(governor.get('risk_multiplier'), 1.0), 6),
        'auto_policy_risk_multiplier': round(_safe_float(auto_policy.get('risk_multiplier_override'), 1.0), 6),
        'geometry_tightened': 1 if geometry.get('applied') else 0,
        'execution_error_seen': 1 if isinstance(meta.get('execution_error'), dict) else 0,
    }


def build_live_feature_dict(*, instrument_id: str, side: str, entry: float, sl: float, tp: float, size: float, ts_ms: int, meta: dict[str, Any] | None = None, final_decision: str | None = None) -> dict[str, Any]:
    meta = dict(meta or {})
    fake_signal = type('LiveSignal', (), {
        'instrument_id': instrument_id,
        'side': side,
        'entry': entry,
        'sl': sl,
        'tp': tp,
        'size': size,
        'created_ts': ts_ms,
        'status': str(meta.get('status') or 'pending_review'),
        'meta': meta,
    })()
    return build_feature_dict_from_signal(fake_signal, signal_meta=meta, final_decision=final_decision)


def build_training_rows_from_entities(
    signals: Iterable[Any],
    positions: Iterable[Any],
    ai_rows: Iterable[Any] | None = None,
    close_logs: Iterable[Any] | None = None,
) -> dict[str, TrainingDataset]:
    ai_by_signal: dict[str, Any] = {}
    for row in ai_rows or []:
        signal_id = str(getattr(row, 'signal_id', '') or '')
        if signal_id and signal_id not in ai_by_signal:
            ai_by_signal[signal_id] = row

    signal_list = list(signals)
    signal_by_id: dict[str, Any] = {}
    signal_by_trace: dict[str, Any] = {}
    for signal in signal_list:
        signal_id = str(getattr(signal, 'id', '') or '')
        meta = _signal_meta(signal)
        trace_id = str(meta.get('trace_id') or '')
        if signal_id and signal_id not in signal_by_id:
            signal_by_id[signal_id] = signal
        if trace_id and trace_id not in signal_by_trace:
            signal_by_trace[trace_id] = signal

    position_by_signal: dict[str, Any] = {}
    position_by_trace: dict[str, Any] = {}
    for pos in positions:
        if _safe_float(getattr(pos, 'qty', None)) > 0:
            continue
        sig_id = str(getattr(pos, 'opened_signal_id', '') or '')
        trace_id = str(getattr(pos, 'trace_id', '') or '')
        if sig_id and sig_id not in position_by_signal:
            position_by_signal[sig_id] = pos
        if trace_id and trace_id not in position_by_trace:
            position_by_trace[trace_id] = pos

    fill_rows: list[TrainingRow] = []
    outcome_rows: list[TrainingRow] = []
    fill_labels = Counter()
    outcome_labels = Counter()
    mapped_positions = 0
    mapped_close_logs = 0
    outcome_signal_ids: set[str] = set()

    for signal in signal_list:
        signal_id = str(getattr(signal, 'id', '') or '')
        if not signal_id:
            continue
        meta = _signal_meta(signal)
        final_decision = str(meta.get('final_decision') or ((_extract_decision(meta)).get('decision')) or '').upper()
        if final_decision != 'TAKE':
            continue
        features = build_feature_dict_from_signal(signal, signal_meta=meta, final_decision=final_decision, ai_row=ai_by_signal.get(signal_id))
        trace_id = str(meta.get('trace_id') or '')
        position = position_by_signal.get(signal_id) or (position_by_trace.get(trace_id) if trace_id else None)
        filled = 1 if (str(getattr(signal, 'status', '') or '').lower() == 'executed' or position is not None) else 0
        fill_row = TrainingRow(
            signal_id=signal_id,
            instrument_id=str(getattr(signal, 'instrument_id', '') or 'unknown'),
            target='take_fill',
            label=filled,
            features=features,
            meta={
                'status': str(getattr(signal, 'status', '') or ''),
                'trace_id': trace_id or None,
                'strategy': features.get('strategy'),
                'regime': features.get('regime'),
            },
        )
        fill_rows.append(fill_row)
        fill_labels[filled] += 1

    for log in close_logs or []:
        payload = getattr(log, 'payload', None)
        if not isinstance(payload, dict):
            continue
        signal_id = str(payload.get('signal_id') or '')
        trace_id = str(payload.get('trace_id') or '')
        signal = signal_by_id.get(signal_id) or (signal_by_trace.get(trace_id) if trace_id else None)
        if signal is None:
            continue
        meta = _signal_meta(signal)
        final_decision = str(meta.get('final_decision') or ((_extract_decision(meta)).get('decision')) or '').upper()
        if final_decision != 'TAKE':
            continue
        signal_id = str(getattr(signal, 'id', '') or signal_id)
        features = build_feature_dict_from_signal(signal, signal_meta=meta, final_decision=final_decision, ai_row=ai_by_signal.get(signal_id))
        diagnostics = dict(payload.get('exit_diagnostics') or {}) if isinstance(payload.get('exit_diagnostics'), dict) else {}
        excursion = dict(payload.get('excursion') or {}) if isinstance(payload.get('excursion'), dict) else {}
        realized = _safe_float(payload.get('net_pnl'), _safe_float(payload.get('gross_pnl')))
        label = 1 if realized > 0 else 0
        outcome_features = dict(features)
        outcome_features['filled'] = 1
        outcome_features['opened_qty'] = round(_safe_float(payload.get('opened_qty'), _safe_float(payload.get('qty'))), 6)
        outcome_features['holding_minutes'] = round(max(0.0, (_safe_float(payload.get('closed_ts')) - _safe_float(payload.get('opened_ts'))) / 60000.0), 4)
        outcome_features['entry_fee_est'] = round(_safe_float(payload.get('entry_fee_est')), 6)
        outcome_features['exit_fee_est'] = round(_safe_float(payload.get('exit_fee_est')), 6)
        outcome_features['total_fees_est'] = round(_safe_float(payload.get('fees_est')), 6)
        outcome_features['mfe_pct'] = round(_safe_float(diagnostics.get('mfe_pct'), _safe_float(excursion.get('mfe_pct'))), 6)
        outcome_features['mae_pct'] = round(_safe_float(diagnostics.get('mae_pct'), _safe_float(excursion.get('mae_pct'))), 6)
        outcome_features['bars_held'] = _safe_int(diagnostics.get('bars_held'))
        outcome_features['hold_utilization_pct'] = round(_safe_float(diagnostics.get('hold_utilization_pct')), 6)
        outcome_features['realized_rr_multiple'] = round(_safe_float(diagnostics.get('realized_rr_multiple')), 6)
        outcome_features['fee_load_pct'] = round(_safe_float(diagnostics.get('fee_load_pct')), 6)
        outcome_row = TrainingRow(
            signal_id=signal_id,
            instrument_id=str(getattr(signal, 'instrument_id', '') or payload.get('instrument_id') or 'unknown'),
            target='trade_outcome',
            label=label,
            features=outcome_features,
            meta={
                'realized_pnl': round(realized, 6),
                'trace_id': trace_id or None,
                'strategy': features.get('strategy'),
                'regime': features.get('regime'),
                'close_reason': str(payload.get('reason') or ''),
                'closed_ts': _safe_int(payload.get('closed_ts') or getattr(log, 'ts', None)),
            },
        )
        outcome_rows.append(outcome_row)
        outcome_labels[label] += 1
        outcome_signal_ids.add(signal_id)
        mapped_close_logs += 1

    if not outcome_rows:
        for signal in signal_list:
            signal_id = str(getattr(signal, 'id', '') or '')
            if not signal_id:
                continue
            meta = _signal_meta(signal)
            final_decision = str(meta.get('final_decision') or ((_extract_decision(meta)).get('decision')) or '').upper()
            if final_decision != 'TAKE':
                continue
            trace_id = str(meta.get('trace_id') or '')
            position = position_by_signal.get(signal_id) or (position_by_trace.get(trace_id) if trace_id else None)
            if position is None:
                continue
            mapped_positions += 1
            realized = _safe_float(getattr(position, 'realized_pnl', None))
            label = 1 if realized > 0 else 0
            features = build_feature_dict_from_signal(signal, signal_meta=meta, final_decision=final_decision, ai_row=ai_by_signal.get(signal_id))
            outcome_features = dict(features)
            outcome_features['filled'] = 1
            outcome_features['opened_qty'] = round(_safe_float(getattr(position, 'opened_qty', None), _safe_float(getattr(position, 'qty', None))), 6)
            outcome_features['holding_minutes'] = round(max(0.0, (_safe_float(getattr(position, 'updated_ts', None)) - _safe_float(getattr(position, 'opened_ts', None))) / 60000.0), 4)
            outcome_features['entry_fee_est'] = round(_safe_float(getattr(position, 'entry_fee_est', None)), 6)
            outcome_features['total_fees_est'] = round(_safe_float(getattr(position, 'total_fees_est', None)), 6)
            outcome_features['mfe_pct'] = round(_safe_float(getattr(position, 'mfe_pct', None)), 6)
            outcome_features['mae_pct'] = round(_safe_float(getattr(position, 'mae_pct', None)), 6)
            outcome_row = TrainingRow(
                signal_id=signal_id,
                instrument_id=str(getattr(signal, 'instrument_id', '') or 'unknown'),
                target='trade_outcome',
                label=label,
                features=outcome_features,
                meta={
                    'realized_pnl': round(realized, 6),
                    'trace_id': trace_id or None,
                    'strategy': features.get('strategy'),
                    'regime': features.get('regime'),
                },
            )
            outcome_rows.append(outcome_row)
            outcome_labels[label] += 1
            outcome_signal_ids.add(signal_id)

    return {
        'take_fill': TrainingDataset(
            target='take_fill',
            rows=fill_rows,
            lookback_days=0,
            stats={
                'labels': dict(fill_labels),
                'mapped_positions': mapped_positions,
            },
        ),
        'trade_outcome': TrainingDataset(
            target='trade_outcome',
            rows=outcome_rows,
            lookback_days=0,
            stats={
                'labels': dict(outcome_labels),
                'mapped_positions': mapped_positions,
                'mapped_close_logs': mapped_close_logs,
                'unique_outcome_signals': len(outcome_signal_ids),
            },
        ),
    }


def build_training_datasets(db: Session, *, lookback_days: int = 120) -> dict[str, TrainingDataset]:
    cutoff = _cutoff_ms(lookback_days)
    signals = (
        db.query(Signal)
        .filter(Signal.created_ts >= cutoff)
        .order_by(Signal.created_ts.asc())
        .all()
    )
    positions = (
        db.query(Position)
        .filter(Position.updated_ts >= cutoff)
        .order_by(Position.updated_ts.asc())
        .all()
    )
    ai_rows = (
        db.query(AIDecisionLog)
        .filter(AIDecisionLog.ts >= cutoff)
        .order_by(AIDecisionLog.ts.asc())
        .all()
    )
    close_logs = (
        db.query(DecisionLog)
        .filter(DecisionLog.type == 'position_closed', DecisionLog.ts >= cutoff)
        .order_by(DecisionLog.ts.asc())
        .all()
    )
    datasets = build_training_rows_from_entities(signals, positions, ai_rows, close_logs)
    for dataset in datasets.values():
        dataset.lookback_days = int(lookback_days)
        dataset.stats = {
            **dataset.stats,
            'signals_scanned': len(signals),
            'positions_scanned': len(positions),
            'ai_rows_scanned': len(ai_rows),
            'close_logs_scanned': len(close_logs),
            'built_at_ts': _now_ms(),
        }
    return datasets
