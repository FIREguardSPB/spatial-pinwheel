import time
from typing import List, Optional

from sqlalchemy.orm import Session

from core.storage.models import Signal


def _pending_review_priority(signal: Signal) -> tuple[int, int, int, int]:
    meta = dict(getattr(signal, 'meta', None) or {})
    review = dict(meta.get('review_readiness') or {})
    approval = 1 if bool(review.get('approval_candidate')) else 0
    queue_priority = int(review.get('queue_priority') or 0)
    created_ts = int(getattr(signal, 'created_ts', 0) or 0)
    ts = int(getattr(signal, 'ts', 0) or 0)
    return (approval, queue_priority, created_ts, ts)


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
    for row in rows:
        if now_ms - int(getattr(row, 'ts', 0) or 0) > max_age_ms:
            continue
        meta = dict(row.meta or {})
        review = dict(meta.get('review_readiness') or {})
        if bool(review.get('approval_candidate')):
            return row
    for row in rows:
        if now_ms - int(getattr(row, 'ts', 0) or 0) <= max_age_ms:
            return row
    return None


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
