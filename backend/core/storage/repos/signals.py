from sqlalchemy.orm import Session
from core.storage.models import Signal
from typing import List, Optional

def list_signals(db: Session, limit: int = 50, status: str = None) -> List[Signal]:
    query = db.query(Signal)
    if status:
        query = query.filter(Signal.status == status)
    return query.order_by(Signal.ts.desc()).limit(limit).all()

def get_signal(db: Session, signal_id: str) -> Optional[Signal]:
    return db.query(Signal).filter(Signal.id == signal_id).first()

def create_signal(db: Session, signal_data: dict) -> Signal:
    signal = Signal(**signal_data)
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal

def update_signal_status(db: Session, signal_id: str, status: str) -> Optional[Signal]:
    signal = get_signal(db, signal_id)
    if signal:
        signal.status = status
        db.commit()
        db.refresh(signal)
    return signal

def count_pending_signals(db: Session, instrument_id: str) -> int:
    return db.query(Signal).filter(
        Signal.instrument_id == instrument_id,
        Signal.status == "pending_review"
    ).count()
