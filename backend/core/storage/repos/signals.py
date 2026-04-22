import time
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from core.storage.models import DecisionLog, Signal


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _age_decay_weight(event_ts: int, now_ms: int, lookback_hours: int) -> float:
    window_ms = int(max(1, lookback_hours)) * 60 * 60 * 1000
    age_ms = max(0, int(now_ms) - int(event_ts or 0))
    if age_ms >= window_ms:
        return 0.0
    remaining = 1.0 - (age_ms / float(window_ms))
    return max(0.25, remaining)


def _pending_review_priority(signal: Signal) -> tuple[int, int, int, int]:
    meta = dict(getattr(signal, 'meta', None) or {})
    review = dict(meta.get('review_readiness') or {})
    approval = 1 if bool(review.get('approval_candidate')) else 0
    queue_priority = int(review.get('queue_priority') or 0)
    confidence_bias = int(review.get('confidence_bias') or 0)
    created_ts = int(getattr(signal, 'created_ts', 0) or 0)
    ts = int(getattr(signal, 'ts', 0) or 0)
    return (approval, queue_priority, confidence_bias, created_ts, ts)


def _execution_feedback_bonus(db: Session, signal: Signal, *, lookback_hours: int = 24) -> int:
    meta = dict(getattr(signal, 'meta', None) or {})
    review = dict(meta.get('review_readiness') or {})
    thesis_tf = str(review.get('thesis_timeframe') or '')
    thesis_type = str(review.get('thesis_type') or '')
    if not thesis_tf or not thesis_type:
        return 0
    cutoff = int(time.time() * 1000) - int(max(1, lookback_hours)) * 60 * 60 * 1000
    rows = (
        db.query(DecisionLog)
        .filter(DecisionLog.ts >= cutoff, DecisionLog.type == 'trade_filled')
        .all()
    )
    bonus = 0
    now_ms = int(time.time() * 1000)
    for row in rows:
        payload = dict(getattr(row, 'payload', None) or {})
        seed = dict(payload.get('execution_quality_seed') or {})
        if str(seed.get('thesis_timeframe') or '') != thesis_tf:
            continue
        seed_review = dict(seed.get('review_readiness') or {})
        if str(seed_review.get('thesis_type') or '') != thesis_type:
            continue
        status = str(seed.get('fill_quality_status') or '')
        if status == 'ok':
            bonus += int(round(15 * _age_decay_weight(getattr(row, 'ts', 0), now_ms, lookback_hours)))
        elif status == 'anomaly':
            bonus -= int(round(10 * _age_decay_weight(getattr(row, 'ts', 0), now_ms, lookback_hours)))
    return bonus


def _outcome_feedback_bonus(db: Session, signal: Signal, *, lookback_hours: int = 24) -> int:
    meta = dict(getattr(signal, 'meta', None) or {})
    review = dict(meta.get('review_readiness') or {})
    thesis_tf = str(review.get('thesis_timeframe') or '')
    thesis_type = str(review.get('thesis_type') or '')
    if not thesis_tf or not thesis_type:
        return 0
    cutoff = int(time.time() * 1000) - int(max(1, lookback_hours)) * 60 * 60 * 1000
    rows = (
        db.query(DecisionLog)
        .filter(DecisionLog.ts >= cutoff, DecisionLog.type == 'position_closed')
        .all()
    )
    bonus = 0
    now_ms = int(time.time() * 1000)
    for row in rows:
        payload = dict(getattr(row, 'payload', None) or {})
        conviction = dict(payload.get('conviction_profile') or {})
        if str(conviction.get('thesis_timeframe') or '') != thesis_tf:
            continue
        notes = ' '.join(str(item) for item in (payload.get('adaptive_exit') or {}).get('notes', [])).lower()
        reason = str(payload.get('reason') or '').upper()
        net_pnl = _safe_float(payload.get('net_pnl'), 0.0)
        if thesis_type == 'continuation' and ('continuation' in notes or reason == 'TP') and net_pnl > 0:
            bonus += int(round(12 * _age_decay_weight(getattr(row, 'ts', 0), now_ms, lookback_hours)))
        elif reason in {'THESIS_DECAY', 'SL', 'STOP'} or net_pnl < 0:
            bonus -= int(round(8 * _age_decay_weight(getattr(row, 'ts', 0), now_ms, lookback_hours)))
    return bonus


def _symbol_thesis_learning_bias(db: Session, signal: Signal, *, lookback_hours: int = 24) -> int:
    meta = dict(getattr(signal, 'meta', None) or {})
    review = dict(meta.get('review_readiness') or {})
    thesis_tf = str(review.get('thesis_timeframe') or '')
    thesis_type = str(review.get('thesis_type') or '')
    instrument_id = str(getattr(signal, 'instrument_id', '') or '')
    if not thesis_tf or not thesis_type or not instrument_id:
        return 0
    cutoff = int(time.time() * 1000) - int(max(1, lookback_hours)) * 60 * 60 * 1000
    rows = (
        db.query(DecisionLog)
        .filter(DecisionLog.ts >= cutoff, DecisionLog.type.in_(['trade_filled', 'position_closed']))
        .all()
    )
    bonus = 0
    now_ms = int(time.time() * 1000)
    for row in rows:
        payload = dict(getattr(row, 'payload', None) or {})
        seed = dict(payload.get('execution_quality_seed') or {})
        seed_review = dict(seed.get('review_readiness') or {})
        conviction = dict(payload.get('conviction_profile') or {})
        payload_tf = str(seed.get('thesis_timeframe') or conviction.get('thesis_timeframe') or '')
        payload_type = str(seed_review.get('thesis_type') or '')
        payload_instrument = str(payload.get('instrument_id') or '')
        if payload_tf != thesis_tf or payload_type != thesis_type or payload_instrument != instrument_id:
            continue
        if str(getattr(row, 'type', '')) == 'trade_filled':
            if str(seed.get('fill_quality_status') or '') == 'ok':
                bonus += int(round(20 * _age_decay_weight(getattr(row, 'ts', 0), now_ms, lookback_hours)))
            elif str(seed.get('fill_quality_status') or '') == 'anomaly':
                bonus -= int(round(12 * _age_decay_weight(getattr(row, 'ts', 0), now_ms, lookback_hours)))
        else:
            net_pnl = _safe_float(payload.get('net_pnl'), 0.0)
            reason = str(payload.get('reason') or '').upper()
            if net_pnl > 0 and reason in {'TP', 'TIME_STOP', 'SESSION_END'}:
                bonus += int(round(18 * _age_decay_weight(getattr(row, 'ts', 0), now_ms, lookback_hours)))
            elif net_pnl < 0 or reason in {'THESIS_DECAY', 'SL', 'STOP'}:
                bonus -= int(round(12 * _age_decay_weight(getattr(row, 'ts', 0), now_ms, lookback_hours)))
    return bonus


def _regime_aware_learning_bias(db: Session, signal: Signal, *, lookback_hours: int = 24) -> int:
    meta = dict(getattr(signal, 'meta', None) or {})
    review = dict(meta.get('review_readiness') or {})
    conviction = dict(meta.get('conviction_profile') or {})
    instrument_id = str(getattr(signal, 'instrument_id', '') or '')
    thesis_tf = str(review.get('thesis_timeframe') or '')
    thesis_type = str(review.get('thesis_type') or '')
    regime = str(conviction.get('regime') or meta.get('market_regime') or '')
    if not instrument_id or not thesis_tf or not thesis_type or not regime:
        return 0
    cutoff = int(time.time() * 1000) - int(max(1, lookback_hours)) * 60 * 60 * 1000
    rows = (
        db.query(DecisionLog)
        .filter(DecisionLog.ts >= cutoff, DecisionLog.type.in_(['trade_filled', 'position_closed']))
        .all()
    )
    bonus = 0
    now_ms = int(time.time() * 1000)
    for row in rows:
        payload = dict(getattr(row, 'payload', None) or {})
        payload_instrument = str(payload.get('instrument_id') or '')
        seed = dict(payload.get('execution_quality_seed') or {})
        seed_review = dict(seed.get('review_readiness') or {})
        payload_conviction = dict(payload.get('conviction_profile') or seed.get('conviction_profile') or {})
        payload_tf = str(seed.get('thesis_timeframe') or payload_conviction.get('thesis_timeframe') or '')
        payload_type = str(seed_review.get('thesis_type') or '')
        payload_regime = str(payload_conviction.get('regime') or '')
        if payload_instrument != instrument_id or payload_tf != thesis_tf or payload_type != thesis_type or payload_regime != regime:
            continue
        if str(getattr(row, 'type', '')) == 'trade_filled':
            if str(seed.get('fill_quality_status') or '') == 'ok':
                bonus += int(round(10 * _age_decay_weight(getattr(row, 'ts', 0), now_ms, lookback_hours)))
            elif str(seed.get('fill_quality_status') or '') == 'anomaly':
                bonus -= int(round(6 * _age_decay_weight(getattr(row, 'ts', 0), now_ms, lookback_hours)))
        else:
            net_pnl = _safe_float(payload.get('net_pnl'), 0.0)
            if net_pnl > 0:
                bonus += int(round(10 * _age_decay_weight(getattr(row, 'ts', 0), now_ms, lookback_hours)))
            elif net_pnl < 0:
                bonus -= int(round(8 * _age_decay_weight(getattr(row, 'ts', 0), now_ms, lookback_hours)))
    return bonus


def _instrument_fatigue_bias(db: Session, signal: Signal, *, lookback_hours: int = 6) -> int:
    instrument_id = str(getattr(signal, 'instrument_id', '') or '')
    if not instrument_id:
        return 0
    cutoff = int(time.time() * 1000) - int(max(1, lookback_hours)) * 60 * 60 * 1000
    rows = (
        db.query(DecisionLog)
        .filter(DecisionLog.ts >= cutoff, DecisionLog.type.in_(['trade_filled', 'position_closed']))
        .all()
    )
    touches = 0
    negative = 0
    for row in rows:
        payload = dict(getattr(row, 'payload', None) or {})
        if str(payload.get('instrument_id') or '') != instrument_id:
            continue
        touches += 1
        if str(getattr(row, 'type', '') or '') == 'position_closed' and _safe_float(payload.get('net_pnl'), 0.0) <= 0:
            negative += 1
    if touches <= 2:
        return 0
    penalty = min(18, (touches - 2) * 4 + negative * 3)
    return -penalty


def _early_failure_cluster_bias(db: Session, signal: Signal, *, lookback_hours: int = 6) -> int:
    meta = dict(getattr(signal, 'meta', None) or {})
    review = dict(meta.get('review_readiness') or {})
    thesis_tf = str(review.get('thesis_timeframe') or '')
    thesis_type = str(review.get('thesis_type') or '')
    instrument_id = str(getattr(signal, 'instrument_id', '') or '')
    if not thesis_tf or not thesis_type:
        return 0
    cutoff = int(time.time() * 1000) - int(max(1, lookback_hours)) * 60 * 60 * 1000
    rows = (
        db.query(DecisionLog)
        .filter(DecisionLog.ts >= cutoff, DecisionLog.type == 'position_closed')
        .all()
    )
    penalty = 0
    for row in rows:
        payload = dict(getattr(row, 'payload', None) or {})
        conviction = dict(payload.get('conviction_profile') or {})
        review_ctx = dict(payload.get('review_readiness') or {})
        if str(conviction.get('thesis_timeframe') or review_ctx.get('thesis_timeframe') or '') != thesis_tf:
            continue
        if str(review_ctx.get('thesis_type') or '') != thesis_type:
            continue
        same_instrument = str(payload.get('instrument_id') or '') == instrument_id
        diag = dict(payload.get('exit_diagnostics') or {})
        if str(diag.get('edge_decay_state') or '') != 'early_failure':
            continue
        bars_held = int(diag.get('bars_held') or 0)
        if bars_held > 2:
            continue
        penalty += 5 if same_instrument else 3
    return -min(15, penalty)


def _thesis_reentry_bias(db: Session, signal: Signal, *, lookback_hours: int = 6) -> int:
    meta = dict(getattr(signal, 'meta', None) or {})
    review = dict(meta.get('review_readiness') or {})
    thesis_tf = str(review.get('thesis_timeframe') or '')
    thesis_type = str(review.get('thesis_type') or '')
    selection_reason = str(review.get('selection_reason') or '')
    instrument_id = str(getattr(signal, 'instrument_id', '') or '')
    if thesis_tf not in {'5m', '15m'} or thesis_type not in {'continuation', 'timeframe_signal', 'context_alignment'} or selection_reason not in {'requested', 'confirmation'}:
        return 0
    cutoff = int(time.time() * 1000) - int(max(1, lookback_hours)) * 60 * 60 * 1000
    rows = (
        db.query(DecisionLog)
        .filter(DecisionLog.ts >= cutoff, DecisionLog.type == 'position_closed')
        .all()
    )
    for row in rows:
        payload = dict(getattr(row, 'payload', None) or {})
        review_ctx = dict(payload.get('review_readiness') or {})
        diag = dict(payload.get('exit_diagnostics') or {})
        if str(payload.get('instrument_id') or '') != instrument_id:
            continue
        if str(review_ctx.get('thesis_timeframe') or '') != thesis_tf:
            continue
        if str(review_ctx.get('thesis_type') or '') != thesis_type:
            continue
        if str(diag.get('edge_decay_state') or '') != 'early_failure':
            continue
        if int(diag.get('bars_held') or 0) > 2:
            continue
        return 8
    return 0


def _diversification_bias(db: Session, signal: Signal) -> int:
    instrument_id = str(getattr(signal, 'instrument_id', '') or '')
    if not instrument_id:
        return 0
    active_rows = (
        db.query(Signal)
        .filter(Signal.status.in_(['pending_review', 'approved', 'executed']))
        .all()
    )
    same_instrument = 0
    for row in active_rows:
        if str(getattr(row, 'instrument_id', '') or '') == instrument_id:
            same_instrument += 1
    if same_instrument <= 1:
        return 6
    if same_instrument == 2:
        return 0
    return -6


def _correlation_nudge(db: Session, signal: Signal) -> int:
    meta = dict(getattr(signal, 'meta', None) or {})
    review = dict(meta.get('review_readiness') or {})
    thesis_tf = str(review.get('thesis_timeframe') or '')
    thesis_type = str(review.get('thesis_type') or '')
    side = str(review.get('side') or '')
    if not thesis_tf or not thesis_type or not side:
        return 0
    active_rows = (
        db.query(Signal)
        .filter(Signal.status.in_(['pending_review', 'approved', 'executed']))
        .all()
    )
    overlaps = 0
    for row in active_rows:
        if row is signal:
            continue
        row_meta = dict(getattr(row, 'meta', None) or {})
        row_review = dict(row_meta.get('review_readiness') or {})
        if str(row_review.get('thesis_timeframe') or '') == thesis_tf and str(row_review.get('thesis_type') or '') == thesis_type and str(row_review.get('side') or '') == side:
            overlaps += 1
    if overlaps == 0:
        return 4
    if overlaps == 1:
        return 0
    return -6


def _session_phase(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(int(ts_ms or 0) / 1000, tz=timezone.utc)
    minute = dt.hour * 60 + dt.minute
    if minute < 7 * 60:
        return 'overnight'
    if minute < 11 * 60:
        return 'early'
    if minute < 15 * 60:
        return 'midday'
    if minute < 20 * 60:
        return 'late'
    return 'overnight'


def _session_phase_bias(signal: Signal) -> int:
    phase = _session_phase(getattr(signal, 'ts', 0) or 0)
    meta = dict(getattr(signal, 'meta', None) or {})
    review = dict(meta.get('review_readiness') or {})
    thesis_tf = str(review.get('thesis_timeframe') or '')
    selection_reason = str(review.get('selection_reason') or '')
    if thesis_tf == '15m' and selection_reason in {'requested', 'confirmation'}:
        if phase == 'midday':
            return 6
        if phase == 'late':
            return -4
    if thesis_tf == '5m' and phase == 'early':
        return 4
    return 0


def _throughput_preserving_bonus(signal: Signal) -> int:
    meta = dict(getattr(signal, 'meta', None) or {})
    review = dict(meta.get('review_readiness') or {})
    thesis_tf = str(review.get('thesis_timeframe') or '')
    selection_reason = str(review.get('selection_reason') or '')
    queue_priority = int(review.get('queue_priority') or 0)
    approval_candidate = bool(review.get('approval_candidate'))
    if approval_candidate and thesis_tf in {'5m', '15m'} and selection_reason in {'requested', 'confirmation'} and queue_priority >= 95:
        return 6
    return 0


def _confidence_shaping_bias(db: Session, signal: Signal) -> int:
    return (
        _execution_feedback_bonus(db, signal)
        + _outcome_feedback_bonus(db, signal)
        + _symbol_thesis_learning_bias(db, signal)
        + _regime_aware_learning_bias(db, signal)
        + _instrument_fatigue_bias(db, signal)
        + _early_failure_cluster_bias(db, signal)
        + _thesis_reentry_bias(db, signal)
        + _diversification_bias(db, signal)
        + _correlation_nudge(db, signal)
        + _session_phase_bias(signal)
        + _throughput_preserving_bonus(signal)
    )


def _apply_confidence_shaping(db: Session, signal: Signal) -> None:
    meta = dict(getattr(signal, 'meta', None) or {})
    review = dict(meta.get('review_readiness') or {})
    if not review:
        return
    bias = int(_confidence_shaping_bias(db, signal))
    review['confidence_bias'] = bias
    review['confidence_multiplier'] = round(max(0.8, min(1.35, 1.0 + (bias / 100.0))), 2)
    meta['review_readiness'] = review
    signal.meta = meta


def list_signals(db: Session, limit: int = 50, status: str = None) -> List[Signal]:
    query = db.query(Signal)
    if status:
        query = query.filter(Signal.status == status)
    rows = query.order_by(Signal.created_ts.desc(), Signal.ts.desc()).limit(limit).all()
    if status == 'pending_review':
        for row in rows:
            _apply_confidence_shaping(db, row)
        return sorted(rows, key=_pending_review_priority, reverse=True)
    return rows


def get_top_pending_review_candidate(db: Session, *, ttl_sec: int = 900) -> Optional[Signal]:
    rows = list_signals(db, limit=50, status='pending_review')
    now_ms = int(time.time() * 1000)
    max_age_ms = max(1, int(ttl_sec)) * 1000
    fresh_rows = [row for row in rows if now_ms - int(getattr(row, 'ts', 0) or 0) <= max_age_ms]
    if not fresh_rows:
        return None
    approval_rows = []
    for row in fresh_rows:
        meta = dict(row.meta or {})
        review = dict(meta.get('review_readiness') or {})
        if bool(review.get('approval_candidate')):
            approval_rows.append(row)
    if approval_rows:
        return max(approval_rows, key=lambda row: (_pending_review_priority(row), _confidence_shaping_bias(db, row)))
    return max(fresh_rows, key=lambda row: (_pending_review_priority(row), _confidence_shaping_bias(db, row)))


def get_oldest_approved_signal(db: Session) -> Optional[Signal]:
    return (
        db.query(Signal)
        .filter(Signal.status == 'approved')
        .order_by(Signal.ts.asc())
        .first()
    )


def detect_reject_storm(db: Session, *, lookback_minutes: int = 60) -> bool:
    cutoff = int(time.time() * 1000) - int(max(1, lookback_minutes)) * 60 * 1000
    created = db.query(Signal).filter(Signal.created_ts >= cutoff).count()
    rejected = db.query(Signal).filter(Signal.created_ts >= cutoff, Signal.status == 'rejected').count()
    runtime_guards = db.query(DecisionLog).filter(DecisionLog.ts >= cutoff, DecisionLog.type == 'auto_runtime_guard').count()
    return created >= 10 and rejected >= max(8, int(created * 0.75)) and runtime_guards >= max(5, int(created * 0.5))


def get_signal(db: Session, signal_id: str) -> Optional[Signal]:
    return db.query(Signal).filter(Signal.id == signal_id).first()


def create_signal(db: Session, signal_data: dict, *, commit: bool = True) -> Signal:
    signal = Signal(**signal_data)
    db.add(signal)
    if commit:
        db.commit()
        db.refresh(signal)
    else:
        db.flush()
    return signal


def update_signal_status(db: Session, signal_id: str, status: str, *, commit: bool = True) -> Optional[Signal]:
    signal = get_signal(db, signal_id)
    if signal:
        signal.status = status
        if commit:
            db.commit()
            db.refresh(signal)
        else:
            db.flush()
    return signal


def expire_stale_pending_signals(
    db: Session,
    instrument_id: str,
    *,
    now_ms: int | None = None,
    ttl_sec: int = 900,
    terminal_status: str = 'expired',
) -> int:
    now_ms = int(now_ms or time.time() * 1000)
    threshold_ms = now_ms - max(1, int(ttl_sec)) * 1000
    rows = (
        db.query(Signal)
        .filter(
            Signal.instrument_id == instrument_id,
            Signal.status == 'pending_review',
            Signal.ts <= threshold_ms,
        )
        .all()
    )
    updated = 0
    for row in rows:
        row.status = terminal_status
        meta = dict(row.meta or {})
        meta.setdefault('pending_expired_reason', 'ttl_exceeded')
        meta['pending_expired_ts'] = now_ms
        meta['pending_ttl_sec'] = int(ttl_sec)
        row.meta = meta
        updated += 1
    if updated:
        db.commit()
    return updated


def count_pending_signals(
    db: Session,
    instrument_id: str,
    *,
    ttl_sec: int = 900,
    max_pending: int | None = None,
) -> int:
    expire_stale_pending_signals(db, instrument_id, ttl_sec=ttl_sec)
    count = (
        db.query(Signal)
        .filter(Signal.instrument_id == instrument_id, Signal.status == 'pending_review')
        .count()
    )
    if max_pending is None:
        return count
    return min(count, int(max_pending))


def replace_weaker_pending_signal(db: Session, instrument_id: str, *, incoming_priority: int, ttl_sec: int = 900) -> bool:
    expire_stale_pending_signals(db, instrument_id, ttl_sec=ttl_sec)
    rows = (
        db.query(Signal)
        .filter(Signal.instrument_id == instrument_id, Signal.status == 'pending_review')
        .all()
    )
    if not rows:
        return False
    weakest = min(rows, key=_pending_review_priority)
    weakest_priority = _pending_review_priority(weakest)[1]
    if int(incoming_priority) <= int(weakest_priority):
        return False
    weakest.status = 'expired'
    meta = dict(weakest.meta or {})
    meta['pending_replaced_by_stronger_candidate'] = True
    meta['pending_replacement_priority'] = int(incoming_priority)
    weakest.meta = meta
    db.commit()
    return True



def count_signals(db: Session, status: str = None) -> int:
    query = db.query(Signal)
    if status:
        query = query.filter(Signal.status == status)
    return int(query.count())


def latest_signal_ts(db: Session, status: str = None) -> int | None:
    query = db.query(Signal.created_ts)
    if status:
        query = query.filter(Signal.status == status)
    row = query.order_by(Signal.created_ts.desc()).first()
    return int(row[0]) if row and row[0] is not None else None
