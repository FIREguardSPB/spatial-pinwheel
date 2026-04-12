from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from core.events.bus import bus
from core.services.paper_audit import build_paper_audit
from core.storage.models import AccountSnapshot, DecisionLog, Order, Position, Settings, Signal, Trade
from core.storage.session import get_db
from core.storage.decision_log_utils import append_decision_log_best_effort

router = APIRouter(dependencies=[Depends(verify_token)])


@router.post('/reset')
async def reset_paper_state(db: Session = Depends(get_db)):
    settings = db.query(Settings).first()
    trade_mode = str(getattr(settings, 'trade_mode', 'review') or 'review')
    if 'paper' not in trade_mode:
        raise HTTPException(status_code=409, detail='Paper reset is allowed only in paper modes')

    counts = {
        'signals': db.query(Signal).count(),
        'orders': db.query(Order).count(),
        'trades': db.query(Trade).count(),
        'positions': db.query(Position).count(),
        'decision_logs': db.query(DecisionLog).count(),
        'account_snapshots': db.query(AccountSnapshot).count(),
    }

    db.query(Trade).delete(synchronize_session=False)
    db.query(Order).delete(synchronize_session=False)
    db.query(Position).delete(synchronize_session=False)
    db.query(Signal).delete(synchronize_session=False)
    db.query(AccountSnapshot).delete(synchronize_session=False)
    db.query(DecisionLog).delete(synchronize_session=False)

    now_ms = int(time.time() * 1000)
    balance = float(getattr(settings, 'account_balance', 100000) or 100000)
    db.add(AccountSnapshot(
        ts=now_ms,
        balance=balance,
        equity=balance,
        day_pnl=0,
    ))
    db.commit()
    append_decision_log_best_effort(
        log_type='paper_reset',
        message='Paper state reset by operator',
        payload={'counts_before': counts, 'balance_after_reset': balance},
        ts_ms=now_ms,
    )

    try:
        await bus.publish('state_reset', {'ts': now_ms, 'mode': trade_mode})
        await bus.publish('orders_updated', {'reset': True, 'ts': now_ms})
        await bus.publish('positions_updated', {'reset': True, 'ts': now_ms})
        await bus.publish('signal_updated', {'reset': True, 'ts': now_ms})
    except Exception:
        pass

    return {'ok': True, 'reset_ts': now_ms, 'trade_mode': trade_mode, 'counts_before': counts, 'balance_after_reset': balance}


@router.get('/audit')
async def get_paper_audit(days: int = Query(30, ge=3, le=180), db: Session = Depends(get_db)):
    settings = db.query(Settings).first()
    trade_mode = str(getattr(settings, 'trade_mode', 'review') or 'review') if settings else 'review'
    if 'paper' not in trade_mode:
        raise HTTPException(status_code=409, detail='Paper audit is available only in paper modes')
    return build_paper_audit(db, days=days)
