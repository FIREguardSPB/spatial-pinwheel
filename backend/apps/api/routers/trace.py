from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from core.storage.models import DecisionLog, Order, Position, PositionExcursion, Signal, Trade
from core.storage.session import get_db

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get('/{trace_id}')
async def get_trace(trace_id: str, db: Session = Depends(get_db)):
    signals = [s for s in db.query(Signal).order_by(Signal.created_ts.desc()).limit(5000).all() if isinstance(s.meta, dict) and (s.meta.get('trace_id') == trace_id)]
    if not signals:
        raise HTTPException(status_code=404, detail='Trace not found')
    signal_ids = {s.id for s in signals}
    instrument_ids = {s.instrument_id for s in signals}

    orders = db.query(Order).filter((Order.trace_id == trace_id) | (Order.related_signal_id.in_(signal_ids))).order_by(Order.ts.asc()).all()
    trades = db.query(Trade).filter((Trade.trace_id == trace_id) | (Trade.signal_id.in_(signal_ids))).order_by(Trade.ts.asc()).all()
    positions = db.query(Position).filter((Position.trace_id == trace_id) | (Position.opened_signal_id.in_(signal_ids)) | (Position.instrument_id.in_(instrument_ids))).all()
    excursions = db.query(PositionExcursion).filter((PositionExcursion.trace_id == trace_id) | (PositionExcursion.signal_id.in_(signal_ids)) | (PositionExcursion.instrument_id.in_(instrument_ids))).order_by(PositionExcursion.ts.asc()).limit(2000).all()

    logs = []
    for entry in db.query(DecisionLog).order_by(DecisionLog.ts.asc()).limit(10000).all():
        payload = entry.payload or {}
        if payload.get('trace_id') == trace_id or payload.get('signal_id') in signal_ids or payload.get('instrument_id') in instrument_ids:
            logs.append({
                'id': entry.id,
                'ts': int(entry.ts),
                'type': entry.type,
                'message': entry.message,
                'payload': payload,
            })

    return {
        'trace_id': trace_id,
        'signals': [
            {
                'id': s.id,
                'instrument_id': s.instrument_id,
                'ts': int(s.ts),
                'status': s.status,
                'side': s.side,
                'meta': s.meta or {},
            } for s in signals
        ],
        'orders': [
            {
                'order_id': o.order_id,
                'instrument_id': o.instrument_id,
                'ts': int(o.ts),
                'status': o.status,
                'qty': float(o.qty or 0),
                'strategy': getattr(o, 'strategy', None),
                'trace_id': getattr(o, 'trace_id', None),
            } for o in orders
        ],
        'trades': [
            {
                'trade_id': t.trade_id,
                'instrument_id': t.instrument_id,
                'ts': int(t.ts),
                'qty': float(t.qty or 0),
                'price': float(t.price or 0),
                'strategy': getattr(t, 'strategy', None),
                'trace_id': getattr(t, 'trace_id', None),
            } for t in trades
        ],
        'positions': [
            {
                'instrument_id': p.instrument_id,
                'qty': float(p.qty or 0),
                'avg_price': float(p.avg_price or 0),
                'strategy': getattr(p, 'strategy', None),
                'trace_id': getattr(p, 'trace_id', None),
                'opened_signal_id': p.opened_signal_id,
                'opened_order_id': p.opened_order_id,
                'closed_order_id': p.closed_order_id,
            } for p in positions
        ],
        'excursions': [
            {
                'ts': int(e.ts),
                'instrument_id': e.instrument_id,
                'phase': e.phase,
                'bar_index': e.bar_index,
                'mark_price': float(e.mark_price or 0),
                'lifecycle_pnl': float(e.lifecycle_pnl or 0),
                'mfe_total_pnl': float(e.mfe_total_pnl or 0),
                'mae_total_pnl': float(e.mae_total_pnl or 0),
                'mfe_pct': float(e.mfe_pct or 0),
                'mae_pct': float(e.mae_pct or 0),
            } for e in excursions
        ],
        'logs': logs,
    }
