"""
P6-02: Trades journal API — история закрытых позиций (round-trip trades).

Frontend TradesPage ожидает: id, ts, instrument_id, side, entry_price,
close_price, qty, realized_pnl, close_reason, duration_sec, strategy,
ai_decision, ai_confidence, de_score.

Источники данных:
- Position (qty=0) → entry_price (avg_price), realized_pnl, side, duration
- DecisionLog (type=position_closed) → close_price, close_reason, qty
- Signal (status=executed) → strategy, AI decision, DE score
"""
from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, asc
from sqlalchemy.orm import Session

from core.storage.models import Position, Signal, DecisionLog
from core.storage.session import get_db
from apps.api.deps import verify_token

router = APIRouter(dependencies=[Depends(verify_token)])


def _find_close_log(db: Session, instrument_id: str, around_ts: int) -> dict:
    """Find DecisionLog entry for position close, matching instrument and time."""
    log = (
        db.query(DecisionLog)
        .filter(
            DecisionLog.type == "position_closed",
            DecisionLog.ts >= around_ts - 60_000,  # within 1 minute of close
            DecisionLog.ts <= around_ts + 60_000,
        )
        .order_by(desc(DecisionLog.ts))
        .all()
    )
    for entry in log:
        payload = entry.payload or {}
        if payload.get("instrument_id") == instrument_id:
            return payload
    return {}


def _find_signal(db: Session, instrument_id: str, opened_ts: int) -> Signal | None:
    """Find the executed signal closest to position open time."""
    return (
        db.query(Signal)
        .filter(
            Signal.instrument_id == instrument_id,
            Signal.status == "executed",
            Signal.ts >= opened_ts - 120_000,
            Signal.ts <= opened_ts + 120_000,
        )
        .order_by(desc(Signal.ts))
        .first()
    )


def _build_entry(pos: Position, close_payload: dict, signal: Signal | None) -> dict[str, Any]:
    entry_price = float(pos.avg_price or 0)
    realized_pnl = float(pos.realized_pnl or 0)

    close_price = close_payload.get("close_price", 0.0)
    close_reason = close_payload.get("reason", "")
    closed_qty = close_payload.get("qty") or close_payload.get("closed_qty") or 0

    duration_sec = 0
    if pos.opened_ts and pos.updated_ts:
        duration_sec = max(0, int((int(pos.updated_ts) - int(pos.opened_ts)) / 1000))

    meta = (signal.meta or {}) if signal else {}
    ai_dec = meta.get("ai_decision", {})
    de_data = meta.get("decision", {})

    return {
        "id":             f"{pos.instrument_id}_{pos.opened_ts}",
        "ts":             int(pos.opened_ts or 0),
        "instrument_id":  pos.instrument_id,
        "side":           pos.side,
        "entry_price":    round(entry_price, 4),
        "close_price":    round(float(close_price), 4) if close_price else 0.0,
        "qty":            int(closed_qty) if closed_qty else 0,
        "realized_pnl":   round(realized_pnl, 2),
        "close_reason":   close_reason,
        "duration_sec":   duration_sec,
        "strategy":       meta.get("strategy", de_data.get("strategy", "")),
        "ai_decision":    ai_dec.get("decision", ""),
        "ai_confidence":  ai_dec.get("confidence"),
        "de_score":       de_data.get("score_pct") or de_data.get("score"),
    }


@router.get("")
async def list_trades(
    limit: int      = Query(100, ge=1, le=1000),
    offset: int     = Query(0, ge=0),
    instrument: str = Query(None),
    side: str       = Query(None),
    outcome: str    = Query(None),
    from_ts: int    = Query(None),
    to_ts: int      = Query(None),
    sort_dir: str   = Query("desc"),
    db: Session     = Depends(get_db),
):
    q = db.query(Position).filter(Position.qty == 0, Position.realized_pnl.isnot(None))
    if instrument:
        q = q.filter(Position.instrument_id == instrument)
    if side:
        q = q.filter(Position.side == side.upper())
    if outcome == "profit":
        q = q.filter(Position.realized_pnl > 0)
    elif outcome == "loss":
        q = q.filter(Position.realized_pnl <= 0)
    if from_ts:
        q = q.filter(Position.opened_ts >= from_ts)
    if to_ts:
        q = q.filter(Position.opened_ts <= to_ts)

    q = q.order_by(desc(Position.updated_ts) if sort_dir == "desc" else asc(Position.updated_ts))
    total = q.count()
    positions = q.offset(offset).limit(limit).all()

    items = []
    for pos in positions:
        close_payload = _find_close_log(db, pos.instrument_id, int(pos.updated_ts or 0))
        signal = _find_signal(db, pos.instrument_id, int(pos.opened_ts or 0))
        items.append(_build_entry(pos, close_payload, signal))

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/stats")
async def trade_stats(
    from_ts: int = Query(None),
    to_ts: int   = Query(None),
    db: Session  = Depends(get_db),
):
    q = db.query(Position).filter(Position.qty == 0, Position.realized_pnl.isnot(None))
    if from_ts:
        q = q.filter(Position.opened_ts >= from_ts)
    if to_ts:
        q = q.filter(Position.opened_ts <= to_ts)

    closed = q.all()
    if not closed:
        return {
            "total_trades": 0, "win_rate": 0, "total_pnl": 0,
            "avg_trade_pnl": 0, "best_trade": 0, "worst_trade": 0,
            "profit_factor": None, "avg_duration_sec": 0,
        }

    pnls = [float(p.realized_pnl or 0) for p in closed]
    wins = [x for x in pnls if x > 0]
    losses_sum = abs(sum(x for x in pnls if x <= 0))

    durations = []
    for p in closed:
        if p.opened_ts and p.updated_ts:
            durations.append(max(0, int((int(p.updated_ts) - int(p.opened_ts)) / 1000)))

    return {
        "total_trades":    len(closed),
        "win_rate":        round(len(wins) / len(pnls) * 100, 1),
        "total_pnl":       round(sum(pnls), 2),
        "avg_trade_pnl":   round(sum(pnls) / len(pnls), 2),
        "best_trade":      round(max(pnls), 2),
        "worst_trade":     round(min(pnls), 2),
        "profit_factor":   round(sum(wins) / losses_sum, 2) if losses_sum > 0 else None,
        "avg_duration_sec": round(sum(durations) / len(durations)) if durations else 0,
    }


@router.get("/export")
async def export_trades_csv(
    from_ts: int = Query(None),
    to_ts: int   = Query(None),
    db: Session  = Depends(get_db),
):
    q = db.query(Position).filter(Position.qty == 0).order_by(desc(Position.updated_ts))
    if from_ts:
        q = q.filter(Position.opened_ts >= from_ts)
    if to_ts:
        q = q.filter(Position.opened_ts <= to_ts)

    positions = q.limit(10000).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "instrument", "side", "entry_price", "realized_pnl",
        "duration_sec", "opened_ts", "closed_ts",
    ])
    for p in positions:
        dur = max(0, int((int(p.updated_ts or 0) - int(p.opened_ts or 0)) / 1000))
        writer.writerow([
            p.instrument_id, p.side, round(float(p.avg_price or 0), 4),
            round(float(p.realized_pnl or 0), 2), dur,
            p.opened_ts, p.updated_ts,
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades.csv"},
    )
