import time
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


def _pending_review_priority(signal: Signal) -> tuple[int, int, int, int]:
    meta = dict(getattr(signal, 'meta', None) or {})
    review = dict(meta.get('review_readiness') or {})
    approval = 1 if bool(review.get('approval_candidate')) else 0
    queue_priority = int(review.get('queue_priority') or 0)
    created_ts = int(getattr(signal, 'created_ts', 0) or 0)
    ts = int(getattr(signal, 'ts', 0) or 0)
    return (approval, queue_priority, created_ts, ts)


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
            bonus += 15
        elif status == 'anomaly':
            bonus -= 10
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
    for row in rows:
        payload = dict(getattr(row, 'payload', None) or {})
        conviction = dict(payload.get('conviction_profile') or {})
        if str(conviction.get('thesis_timeframe') or '') != thesis_tf:
            continue
        notes = ' '.join(str(item) for item in (payload.get('adaptive_exit') or {}).get('notes', [])).lower()
        reason = str(payload.get('reason') or '').upper()
        net_pnl = _safe_float(payload.get('net_pnl'), 0.0)
        if thesis_type == 'continuation' and ('continuation' in notes or reason == 'TP') and net_pnl > 0:
            bonus += 12
        elif reason in {'THESIS_DECAY', 'SL', 'STOP'} or net_pnl < 0:
            bonus -= 8
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
                bonus += 20
            elif str(seed.get('fill_quality_status') or '') == 'anomaly':
                bonus -= 12
        else:
            net_pnl = _safe_float(payload.get('net_pnl'), 0.0)
            reason = str(payload.get('reason') or '').upper()
            if net_pnl > 0 and reason in {'TP', 'TIME_STOP', 'SESSION_END'}:
                bonus += 18
            elif net_pnl < 0 or reason in {'THESIS_DECAY', 'SL', 'STOP'}:
                bonus -= 12
    return bonus


def list_signals(db: Session, limit: int = 50, status: str = None) -> List[Signal]:
    query = db.query(Signal)
    if status:
        query = query.filter(Signal.status == status)
    rows = query.order_by(Signal.created_ts.desc(), Signal.ts.desc()).limit(limit).all()
    if status == 'pending_review':
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
        return max(approval_rows, key=lambda row: (_pending_review_priority(row), _execution_feedback_bonus(db, row) + _outcome_feedback_bonus(db, row) + _symbol_thesis_learning_bias(db, row)))
    return max(fresh_rows, key=lambda row: (_pending_review_priority(row), _execution_feedback_bonus(db, row) + _outcome_feedback_bonus(db, row) + _symbol_thesis_learning_bias(db, row)))


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
