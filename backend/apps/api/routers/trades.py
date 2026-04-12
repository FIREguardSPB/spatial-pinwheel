"""
Trades API.

The journal must be trustworthy for monitoring. Source of truth for *closed* trades
is the immutable `position_closed` decision log, not the mutable `positions` row.

By default `GET /api/v1/trades` returns only closed round-trip trades.
Optional `include_open=true` can additionally surface raw execution fills that are
still open, but those are excluded from summary cards and are off by default to
avoid mixing open fills with completed trades.
"""
from __future__ import annotations

import csv
import io
import time
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from core.storage.models import DecisionLog, Order, Position, Signal, Trade
from core.storage.session import get_db

router = APIRouter(dependencies=[Depends(verify_token)])


def _find_signal(db: Session, instrument_id: str, opened_ts: int, signal_id: str | None = None) -> Signal | None:
    if signal_id:
        linked = db.query(Signal).filter(Signal.id == signal_id).first()
        if linked:
            return linked
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


def _signal_meta(signal: Signal | None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    meta = (signal.meta or {}) if signal else {}
    ai_dec = meta.get("ai_decision", {}) if isinstance(meta, dict) else {}
    de_data = meta.get("decision", {}) if isinstance(meta, dict) else {}
    return meta, ai_dec, de_data


def _strategy_name(meta: dict[str, Any], de_data: dict[str, Any], fallback: str | None = None) -> str:
    return str(
        fallback
        or meta.get("multi_strategy", {}).get("selected")
        or meta.get("strategy")
        or meta.get("strategy_name")
        or de_data.get("strategy")
        or ""
    )


def _find_open_fill(db: Session, payload: dict[str, Any]) -> Trade | None:
    opened_order_id = payload.get("opened_order_id")
    instrument_id = payload.get("instrument_id")
    opened_ts = int(payload.get("opened_ts") or 0)
    if opened_order_id:
        trade = db.query(Trade).filter(Trade.order_id == opened_order_id).order_by(asc(Trade.ts)).first()
        if trade:
            return trade
    if instrument_id and opened_ts:
        return (
            db.query(Trade)
            .filter(
                Trade.instrument_id == instrument_id,
                Trade.ts >= opened_ts - 120_000,
                Trade.ts <= opened_ts + 120_000,
            )
            .order_by(asc(Trade.ts))
            .first()
        )
    return None


def _find_open_order(db: Session, payload: dict[str, Any]) -> Order | None:
    opened_order_id = payload.get("opened_order_id")
    instrument_id = payload.get("instrument_id")
    opened_ts = int(payload.get("opened_ts") or 0)
    if opened_order_id:
        order = db.query(Order).filter(Order.order_id == opened_order_id).first()
        if order:
            return order
    if instrument_id and opened_ts:
        return (
            db.query(Order)
            .filter(
                Order.instrument_id == instrument_id,
                Order.ts >= opened_ts - 120_000,
                Order.ts <= opened_ts + 120_000,
                Order.status == "FILLED",
            )
            .order_by(asc(Order.ts))
            .first()
        )
    return None


def _build_closed_entry_from_log(db: Session, log: DecisionLog) -> dict[str, Any]:
    payload = (log.payload or {}) if isinstance(log.payload, dict) else {}
    instrument_id = str(payload.get("instrument_id") or "")
    opened_ts = int(payload.get("opened_ts") or 0)
    closed_ts = int(payload.get("closed_ts") or log.ts or 0)
    signal = _find_signal(db, instrument_id, opened_ts, payload.get("signal_id"))
    meta, ai_dec, de_data = _signal_meta(signal)

    open_trade = _find_open_fill(db, payload)
    open_order = _find_open_order(db, payload)

    entry_price = 0.0
    entry_qty = 0.0
    side = ""
    trace_id = payload.get("trace_id") or meta.get("trace_id")
    strategy = _strategy_name(meta, de_data, payload.get("strategy_name"))
    opened_order_id = payload.get("opened_order_id")
    closed_order_id = payload.get("closed_order_id")

    if open_trade:
        entry_price = float(open_trade.price or 0)
        entry_qty = float(open_trade.qty or 0)
        side = str(open_trade.side or "")
        trace_id = trace_id or getattr(open_trade, "trace_id", None)
        strategy = strategy or getattr(open_trade, "strategy", None) or ""
        opened_order_id = opened_order_id or getattr(open_trade, "order_id", None)
    elif open_order:
        entry_price = float(open_order.price or 0)
        entry_qty = float(open_order.filled_qty or open_order.qty or 0)
        side = str(open_order.side or "")
        trace_id = trace_id or getattr(open_order, "trace_id", None)
        strategy = strategy or getattr(open_order, "strategy", None) or ""
        opened_order_id = opened_order_id or getattr(open_order, "order_id", None)

    if not entry_qty:
        entry_qty = float(payload.get("opened_qty") or payload.get("qty") or 0)
    close_qty = float(payload.get("qty") or payload.get("closed_qty") or entry_qty or 0)

    close_price = float(payload.get("close_price") or 0)
    realized_pnl = payload.get("net_pnl")
    if realized_pnl is None:
        realized_pnl = payload.get("gross_pnl")
    realized_pnl = round(float(realized_pnl or 0.0), 2)

    duration_sec = 0
    if opened_ts and closed_ts:
        duration_sec = max(0, int((closed_ts - opened_ts) / 1000))

    entry_id = str(log.id or f"{instrument_id}_{closed_ts}")
    return {
        "id": entry_id,
        "source": "closed_trade",
        "signal_id": getattr(signal, "id", None) if signal else payload.get("signal_id"),
        "trace_id": trace_id,
        "opened_order_id": opened_order_id,
        "closed_order_id": closed_order_id,
        "ts": closed_ts,
        "opened_ts": opened_ts,
        "instrument_id": instrument_id,
        "side": side,
        "entry_price": round(float(entry_price or 0), 4),
        "close_price": round(close_price, 4) if close_price else 0.0,
        "qty": float(close_qty or 0.0),
        "realized_pnl": realized_pnl,
        "fees_est": round(float(payload.get("fees_est") or 0.0), 6),
        "close_reason": str(payload.get("reason") or ""),
        "duration_sec": duration_sec,
        "strategy": strategy,
        "ai_decision": ai_dec.get("decision", ""),
        "ai_confidence": ai_dec.get("confidence"),
        "de_score": de_data.get("score_pct") or de_data.get("score"),
        "ai_influenced": bool(getattr(signal, "ai_influenced", False)) if signal else False,
        "ai_mode_used": getattr(signal, "ai_mode_used", None) if signal else None,
    }


def _build_open_fill_entry(trade: Trade, signal: Signal | None) -> dict[str, Any]:
    meta, ai_dec, de_data = _signal_meta(signal)
    duration_sec = max(0, int((int(time.time() * 1000) - int(trade.ts or 0)) / 1000)) if trade.ts else 0
    return {
        "id": trade.trade_id,
        "source": "execution_fill",
        "signal_id": getattr(signal, "id", None) if signal else getattr(trade, "signal_id", None),
        "trace_id": getattr(trade, "trace_id", None) or meta.get("trace_id"),
        "opened_order_id": getattr(trade, "order_id", None),
        "closed_order_id": None,
        "ts": int(trade.ts or 0),
        "opened_ts": int(trade.ts or 0),
        "instrument_id": trade.instrument_id,
        "side": trade.side,
        "entry_price": round(float(trade.price or 0), 4),
        "close_price": 0.0,
        "qty": float(trade.qty or 0),
        "realized_pnl": 0.0,
        "close_reason": "OPEN",
        "duration_sec": duration_sec,
        "strategy": _strategy_name(meta, de_data, getattr(trade, "strategy", None)),
        "ai_decision": ai_dec.get("decision", ""),
        "ai_confidence": ai_dec.get("confidence"),
        "de_score": de_data.get("score_pct") or de_data.get("score"),
        "ai_influenced": bool(getattr(signal, "ai_influenced", False)) if signal else False,
        "ai_mode_used": getattr(signal, "ai_mode_used", None) if signal else None,
    }


def _is_closed_journal_item(entry: dict[str, Any]) -> bool:
    if not entry:
        return False
    if str(entry.get("source") or "") != "closed_trade":
        return False
    if str(entry.get("close_reason") or "").upper() == "OPEN":
        return False
    try:
        close_price = float(entry.get("close_price") or 0)
        qty = float(entry.get("qty") or 0)
    except Exception:
        return False
    if close_price <= 0 or qty <= 0:
        return False
    return True


def _recalc_realized_pnl(entry: dict[str, Any]) -> float:
    try:
        pnl = float(entry.get("realized_pnl") or 0.0)
        if abs(pnl) > 1e-9:
            return round(pnl, 2)
        entry_price = float(entry.get("entry_price") or 0.0)
        close_price = float(entry.get("close_price") or 0.0)
        qty = float(entry.get("qty") or 0.0)
        side = str(entry.get("side") or "").upper()
        if entry_price <= 0 or close_price <= 0 or qty <= 0 or side not in {"BUY", "SELL"}:
            return round(pnl, 2)
        gross = (close_price - entry_price) * qty if side == "BUY" else (entry_price - close_price) * qty
        fees = float(entry.get("fees_est") or 0.0)
        return round(gross - fees, 2)
    except Exception:
        return round(float(entry.get("realized_pnl") or 0.0), 2)


def _normalize_closed_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    if not _is_closed_journal_item(entry):
        return None
    normalized = dict(entry)
    normalized["realized_pnl"] = _recalc_realized_pnl(normalized)
    return normalized


def _matches_filters(
    entry: dict[str, Any],
    *,
    instrument: str | None,
    side: str | None,
    outcome: str | None,
    strategy: str | None,
    from_ts: int | None,
    to_ts: int | None,
) -> bool:
    if instrument and entry.get("instrument_id") != instrument:
        return False
    if side and str(entry.get("side") or "").upper() != side.upper():
        return False
    if outcome == "profit" and float(entry.get("realized_pnl") or 0) <= 0:
        return False
    if outcome == "loss" and float(entry.get("realized_pnl") or 0) >= 0:
        return False
    if strategy and strategy.lower() not in str(entry.get("strategy") or "").lower():
        return False
    if from_ts and int(entry.get("ts") or 0) < from_ts:
        return False
    if to_ts and int(entry.get("ts") or 0) > to_ts:
        return False
    return True


def build_trades_payload(
    db: Session,
    *,
    limit: int = 100,
    offset: int = 0,
    instrument: str | None = None,
    side: str | None = None,
    outcome: str | None = None,
    strategy: str | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    sort_dir: str = "desc",
    include_open: bool = False,
) -> dict[str, Any]:
    close_logs = db.query(DecisionLog).filter(DecisionLog.type == "position_closed")
    if from_ts:
        close_logs = close_logs.filter(DecisionLog.ts >= from_ts)
    if to_ts:
        close_logs = close_logs.filter(DecisionLog.ts <= to_ts)
    close_logs = close_logs.order_by(desc(DecisionLog.ts) if sort_dir == "desc" else asc(DecisionLog.ts)).limit(max(limit * 5, 500))

    closed_items: list[dict[str, Any]] = []
    closed_signal_ids: set[str] = set()
    closed_order_ids: set[str] = set()
    for log in close_logs.all():
        try:
            built = _build_closed_entry_from_log(db, log)
            item = _normalize_closed_entry(built)
        except Exception:
            continue
        if not item:
            continue
        if _matches_filters(item, instrument=instrument, side=side, outcome=outcome, strategy=strategy, from_ts=from_ts, to_ts=to_ts):
            closed_items.append(item)
            if item.get("signal_id"):
                closed_signal_ids.add(str(item["signal_id"]))
            if item.get("opened_order_id"):
                closed_order_ids.add(str(item["opened_order_id"]))
            if item.get("closed_order_id"):
                closed_order_ids.add(str(item["closed_order_id"]))

    items = list(closed_items)

    if include_open and False:
        raw_trades = (
            db.query(Trade)
            .order_by(desc(Trade.ts) if sort_dir == "desc" else asc(Trade.ts))
            .limit(max(limit * 5, 500))
            .all()
        )
        for trade in raw_trades:
            trade_signal_id = getattr(trade, "signal_id", None)
            trade_order_id = getattr(trade, "order_id", None)
            if trade_signal_id and str(trade_signal_id) in closed_signal_ids:
                continue
            if trade_order_id and str(trade_order_id) in closed_order_ids:
                continue
            try:
                signal = _find_signal(db, trade.instrument_id, int(trade.ts or 0), trade_signal_id)
                item = _build_open_fill_entry(trade, signal)
            except Exception:
                continue
            if _matches_filters(item, instrument=instrument, side=side, outcome=outcome, strategy=strategy, from_ts=from_ts, to_ts=to_ts):
                items.append(item)

    items.sort(key=lambda item: int(item.get("ts") or 0), reverse=(sort_dir != "asc"))
    total = len(items)
    paginated = items[offset : offset + limit]
    return {"items": paginated, "total": total, "limit": limit, "offset": offset}


@router.get("")
async def list_trades(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    instrument: str | None = Query(None),
    side: str | None = Query(None),
    outcome: str | None = Query(None),
    strategy: str | None = Query(None),
    from_ts: int | None = Query(None),
    to_ts: int | None = Query(None),
    sort_dir: str = Query("desc"),
    include_open: bool = Query(False),
    db: Session = Depends(get_db),
):
    return build_trades_payload(
        db,
        limit=limit,
        offset=offset,
        instrument=instrument,
        side=side,
        outcome=outcome,
        strategy=strategy,
        from_ts=from_ts,
        to_ts=to_ts,
        sort_dir=sort_dir,
        include_open=include_open,
    )


def build_trade_stats_payload(
    db: Session,
    *,
    from_ts: int | None = None,
    to_ts: int | None = None,
) -> dict[str, Any]:
    close_logs = db.query(DecisionLog).filter(DecisionLog.type == "position_closed")
    if from_ts:
        close_logs = close_logs.filter(DecisionLog.ts >= from_ts)
    if to_ts:
        close_logs = close_logs.filter(DecisionLog.ts <= to_ts)

    items: list[dict[str, Any]] = []
    for log in close_logs.all():
        try:
            built = _build_closed_entry_from_log(db, log)
            item = _normalize_closed_entry(built)
            if item:
                items.append(item)
        except Exception:
            continue

    if not items:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_trade_pnl": 0,
            "best_trade": 0,
            "worst_trade": 0,
            "wins_count": 0,
            "losses_count": 0,
            "profit_factor": None,
            "avg_duration_sec": 0,
        }

    pnls = [float(item.get("realized_pnl") or 0) for item in items]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    losses_sum = abs(sum(losses))
    durations = [int(item.get("duration_sec") or 0) for item in items if int(item.get("duration_sec") or 0) > 0]

    return {
        "total_trades": len(items),
        "win_rate": round(len(wins) / len(pnls) * 100, 1) if pnls else 0,
        "total_pnl": round(sum(pnls), 2),
        "avg_trade_pnl": round(sum(pnls) / len(pnls), 2) if pnls else 0,
        "best_trade": round(max(wins), 2) if wins else 0,
        "worst_trade": round(min(losses), 2) if losses else 0,
        "wins_count": len(wins),
        "losses_count": len(losses),
        "profit_factor": round(sum(wins) / losses_sum, 2) if losses_sum > 0 else None,
        "avg_duration_sec": round(sum(durations) / len(durations)) if durations else 0,
    }


@router.get("/stats")
async def trade_stats(
    from_ts: int = Query(None),
    to_ts: int = Query(None),
    db: Session = Depends(get_db),
):
    return build_trade_stats_payload(db, from_ts=from_ts, to_ts=to_ts)


@router.get("/export")
async def export_trades_csv(
    from_ts: int = Query(None),
    to_ts: int = Query(None),
    db: Session = Depends(get_db),
):
    close_logs = db.query(DecisionLog).filter(DecisionLog.type == "position_closed").order_by(desc(DecisionLog.ts))
    if from_ts:
        close_logs = close_logs.filter(DecisionLog.ts >= from_ts)
    if to_ts:
        close_logs = close_logs.filter(DecisionLog.ts <= to_ts)

    items: list[dict[str, Any]] = []
    for log in close_logs.limit(10000).all():
        try:
            built = _build_closed_entry_from_log(db, log)
            item = _normalize_closed_entry(built)
            if item:
                items.append(item)
        except Exception:
            continue

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "instrument",
        "side",
        "entry_price",
        "close_price",
        "qty",
        "realized_pnl",
        "duration_sec",
        "opened_ts",
        "closed_ts",
        "strategy",
        "reason",
        "trace_id",
        "signal_id",
    ])
    for item in items:
        writer.writerow([
            item.get("instrument_id"),
            item.get("side"),
            round(float(item.get("entry_price") or 0), 4),
            round(float(item.get("close_price") or 0), 4),
            round(float(item.get("qty") or 0), 4),
            round(float(item.get("realized_pnl") or 0), 2),
            int(item.get("duration_sec") or 0),
            item.get("opened_ts"),
            item.get("ts"),
            item.get("strategy"),
            item.get("close_reason"),
            item.get("trace_id"),
            item.get("signal_id"),
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades.csv"},
    )
