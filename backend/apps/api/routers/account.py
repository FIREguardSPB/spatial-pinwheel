"""
P6-11: Account API — баланс, equity curve, дневная статистика.

GET /api/v1/account/summary    — баланс, equity, open PnL, day PnL
GET /api/v1/account/history    — equity curve (из account_snapshots)
GET /api/v1/account/daily-stats — реальная дневная статистика из trades
"""
from __future__ import annotations

import datetime as dt
import time
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.config import get_token, settings as cfg
from core.execution.tbank import TBankExecutionEngine
from core.storage.models import AccountSnapshot, Position, Settings, Trade
from core.storage.session import get_db
from apps.api.deps import verify_token

router = APIRouter(dependencies=[Depends(verify_token)])


def _today_ms() -> int:
    today = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return int(today.timestamp() * 1000)


@router.get("/summary")
async def account_summary(db: Session = Depends(get_db)):
    """
    Account balance + equity overview.
    Paper mode: reads from Settings.account_balance + open positions unrealized PnL.
    Live mode: would call TBank adapter (returns paper data as fallback).
    """
    s = db.query(Settings).first()

    trade_mode = getattr(s, "trade_mode", "review") if s else "review"
    mode = "tbank" if cfg.BROKER_PROVIDER == "tbank" and trade_mode == "auto_live" else cfg.BROKER_PROVIDER
    balance = float(getattr(s, "account_balance", 100_000) or 100_000)

    positions = db.query(Position).filter(Position.qty > 0).all()
    open_pnl = sum(float(p.unrealized_pnl or 0) for p in positions)
    equity = balance + open_pnl

    if mode == "tbank":
        try:
            portfolio = await TBankExecutionEngine(db, token=get_token("TBANK_TOKEN") or cfg.TBANK_TOKEN, account_id=get_token("TBANK_ACCOUNT_ID") or cfg.TBANK_ACCOUNT_ID, sandbox=cfg.TBANK_SANDBOX).get_portfolio()
            balance = float(portfolio.get("total_amount_currencies", balance) or balance)
            equity = float(portfolio.get("total_amount_portfolio", equity) or equity)
            open_pnl = round(equity - balance, 2)
        except Exception:
            pass

    # Day PnL from closed positions today (Trade model has no realized_pnl — it's on Position)
    day_pnl = db.query(func.sum(Position.realized_pnl)).filter(
        Position.updated_ts >= _today_ms()
    ).scalar() or 0.0

    # Total PnL all time (from all positions, including closed ones with qty=0)
    total_pnl = db.query(func.sum(Position.realized_pnl)).scalar() or 0.0

    # Max drawdown (rough: from account_snapshots)
    snapshots = db.query(AccountSnapshot).order_by(AccountSnapshot.ts).limit(5000).all()
    max_dd = 0.0
    if snapshots:
        peak = float(snapshots[0].equity or equity)
        for snap in snapshots:
            eq = float(snap.equity or 0)
            peak = max(peak, eq)
            dd = (peak - eq) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)

    return {
        "mode":            mode,
        "balance":         round(balance, 2),
        "equity":          round(equity, 2),
        "open_pnl":        round(open_pnl, 2),
        "day_pnl":         round(float(day_pnl), 2),
        "total_pnl":       round(float(total_pnl), 2),
        "open_positions":  len(positions),
        "max_drawdown_pct": round(max_dd, 2),
        "broker_info": {
            "name":   "T-Bank Invest" if mode == "tbank" else "Paper Trading",
            "type":   "broker" if mode == "tbank" else "virtual",
            "status": "active",
        },
    }


@router.get("/history")
async def account_history(
    period_days: int = Query(30, ge=1, le=365),
    db: Session      = Depends(get_db),
):
    """Equity curve history from account_snapshots."""
    from_ts = int((dt.datetime.now() - dt.timedelta(days=period_days)).timestamp() * 1000)
    snapshots = (
        db.query(AccountSnapshot)
        .filter(AccountSnapshot.ts >= from_ts)
        .order_by(AccountSnapshot.ts)
        .all()
    )
    return {
        "period_days": period_days,
        "points": [
            {
                "ts":      snap.ts,
                "balance": float(snap.balance or 0),
                "equity":  float(snap.equity or 0),
                "day_pnl": float(snap.day_pnl or 0),
            }
            for snap in snapshots
        ],
    }


@router.get("/daily-stats")
async def daily_stats(db: Session = Depends(get_db)):
    """
    P6-11: Real daily stats — replaces hardcoded pnl:125.50 in StatsWidgets.
    Uses Position.realized_pnl for PnL data (Trade model has no pnl field).
    """
    today_ms = _today_ms()

    # Count trades opened today
    trades_count = db.query(Trade).filter(Trade.ts >= today_ms).count()

    # Positions closed today (qty=0 and updated today)
    closed_today = (
        db.query(Position)
        .filter(Position.qty == 0, Position.updated_ts >= today_ms)
        .all()
    )
    pnls = [float(p.realized_pnl or 0) for p in closed_today]
    wins = [p for p in pnls if p > 0]

    open_positions = db.query(Position).filter(Position.qty > 0).count()

    best  = round(max(pnls), 2)  if pnls else 0.0
    worst = round(min(pnls), 2)  if pnls else 0.0

    return {
        "day_pnl":        round(sum(pnls), 2),
        "trades_count":   trades_count,
        "win_rate":       round(len(wins) / len(pnls) * 100, 1) if pnls else 0.0,
        "best_trade":     best,
        "worst_trade":    worst,
        "open_positions": open_positions,
    }
