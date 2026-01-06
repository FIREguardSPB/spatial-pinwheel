from sqlalchemy.orm import Session
from core.storage.models import Order, Trade, Position, DecisionLog
from sqlalchemy.exc import IntegrityError


# --- Orders ---
def create_order(db: Session, order_data: dict) -> Order:
    try:
        order = Order(**order_data)
        db.add(order)
        db.commit()
        db.refresh(order)
        return order
    except IntegrityError:
        db.rollback()
        # Idempotency check: if related_signal_id exists, return existing order
        if order_data.get("related_signal_id"):
            return (
                db.query(Order)
                .filter(Order.related_signal_id == order_data["related_signal_id"])
                .first()
            )
        raise


def list_orders(db: Session, limit: int = 50) -> list[Order]:
    return db.query(Order).order_by(Order.ts.desc()).limit(limit).all()


# --- Trades ---
def create_trade(db: Session, trade_data: dict) -> Trade:
    trade = Trade(**trade_data)
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


def list_trades(db: Session, limit: int = 50) -> list[Trade]:
    return db.query(Trade).order_by(Trade.ts.desc()).limit(limit).all()


# --- Positions ---
def upsert_position(db: Session, pos_data: dict) -> Position:
    pos = db.query(Position).filter(Position.instrument_id == pos_data["instrument_id"]).first()
    if not pos:
        pos = Position(**pos_data)
        db.add(pos)
    else:
        for k, v in pos_data.items():
            setattr(pos, k, v)
    db.commit()
    db.refresh(pos)
    return pos


def list_positions(db: Session) -> list[Position]:
    return db.query(Position).all()


# --- Logs ---
def append_log(db: Session, log_data: dict) -> DecisionLog:
    log = DecisionLog(**log_data)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_logs(db: Session, limit: int = 50) -> list[DecisionLog]:
    return db.query(DecisionLog).order_by(DecisionLog.ts.desc()).limit(limit).all()
