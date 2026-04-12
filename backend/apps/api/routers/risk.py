from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from core.risk.manager import RiskManager
from core.storage.session import get_db
from core.storage.decision_log_utils import append_decision_log_best_effort

router = APIRouter(dependencies=[Depends(verify_token)])


@router.post('/reset_daily')
async def reset_daily_risk(db: Session = Depends(get_db)):
    manager = RiskManager(db)
    before = manager._get_today_realized_pnl()
    now_ms = int(time.time() * 1000)
    db.commit()
    append_decision_log_best_effort(
        log_type='risk_daily_reset',
        message='Daily risk counters reset by operator',
        payload={'before_realized_pnl': before, 'reset_ts': now_ms},
        ts_ms=now_ms,
    )
    return {
        'ok': True,
        'reset_ts': now_ms,
        'before_realized_pnl': round(before, 2),
        'risk_window_start_ms': manager._risk_window_start_ms(),
    }
