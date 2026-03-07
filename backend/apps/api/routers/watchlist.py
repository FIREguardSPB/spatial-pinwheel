"""
P6-09: Watchlist + Instrument search API.

GET  /api/v1/watchlist                    — active watchlist
POST /api/v1/watchlist                    — add instrument
DELETE /api/v1/watchlist/{instrument_id}  — remove
GET  /api/v1/instruments/search?q=        — search (static catalog in mock mode)
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.storage.session import get_db
from apps.api.deps import verify_token

router = APIRouter(dependencies=[Depends(verify_token)])

# ── Static MOEX catalog (mock / offline mode) ─────────────────────────────────
_MOEX_CATALOG = [
    {"instrument_id": "TQBR:SBER",  "ticker": "SBER",  "name": "Сбербанк",          "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:GAZP",  "ticker": "GAZP",  "name": "Газпром",            "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:LKOH",  "ticker": "LKOH",  "name": "Лукойл",             "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:YNDX",  "ticker": "YNDX",  "name": "Яндекс",             "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:ROSN",  "ticker": "ROSN",  "name": "Роснефть",           "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:NVTK",  "ticker": "NVTK",  "name": "Новатэк",            "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:VTBR",  "ticker": "VTBR",  "name": "ВТБ",               "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:MOEX",  "ticker": "MOEX",  "name": "Московская биржа",   "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:GMKN",  "ticker": "GMKN",  "name": "ГМК НорНикель",     "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:TATN",  "ticker": "TATN",  "name": "Татнефть",           "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:SNGS",  "ticker": "SNGS",  "name": "Сургутнефтегаз",    "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:ALRS",  "ticker": "ALRS",  "name": "АЛРОСА",            "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:MGNT",  "ticker": "MGNT",  "name": "Магнит",             "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:AFLT",  "ticker": "AFLT",  "name": "Аэрофлот",          "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:MTSS",  "ticker": "MTSS",  "name": "МТС",               "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:OZON",  "ticker": "OZON",  "name": "OZON",              "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:POLY",  "ticker": "POLY",  "name": "Polymetal",          "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:PLZL",  "ticker": "PLZL",  "name": "Полюс",             "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:FEES",  "ticker": "FEES",  "name": "ФСК ЕЭС",           "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:HYDR",  "ticker": "HYDR",  "name": "РусГидро",          "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:CBOM",  "ticker": "CBOM",  "name": "Московский Кредит", "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:SFIN",  "ticker": "SFIN",  "name": "SFI",               "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:PIKK",  "ticker": "PIKK",  "name": "ПИК",               "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:FIXP",  "ticker": "FIXP",  "name": "Fix Price",          "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:PHOR",  "ticker": "PHOR",  "name": "ФосАгро",           "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:AGRO",  "ticker": "AGRO",  "name": "РусАгро",           "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:SMLT",  "ticker": "SMLT",  "name": "Самолёт",           "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:SGZH",  "ticker": "SGZH",  "name": "Сегежа",            "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:VKCO",  "ticker": "VKCO",  "name": "VK Company",        "exchange": "TQBR", "type": "stock"},
    {"instrument_id": "TQBR:RTKM",  "ticker": "RTKM",  "name": "Ростелеком",        "exchange": "TQBR", "type": "stock"},
]


@router.get("/search")
async def search_instruments(q: str = Query("", min_length=0)):
    """Search MOEX instruments by ticker or name (static catalog)."""
    q_lower = q.lower().strip()
    if not q_lower:
        return {"items": _MOEX_CATALOG[:20]}
    results = [
        item for item in _MOEX_CATALOG
        if q_lower in item["ticker"].lower() or q_lower in item["name"].lower()
    ]
    return {"items": results[:20]}


# ── Watchlist endpoints ───────────────────────────────────────────────────────

class WatchlistAdd(BaseModel):
    instrument_id: str
    ticker: str
    name: str
    exchange: str = "TQBR"


@router.get("")
async def get_watchlist(db: Session = Depends(get_db)):
    """Return active watchlist from DB."""
    from core.storage.models import Watchlist
    items = db.query(Watchlist).filter(Watchlist.is_active == True).order_by(Watchlist.added_ts).all()
    return {
        "items": [
            {
                "instrument_id": w.instrument_id,
                "ticker":        w.ticker,
                "name":          w.name,
                "exchange":      w.exchange,
                "is_active":     w.is_active,
                "added_ts":      w.added_ts,
            }
            for w in items
        ]
    }


@router.post("", status_code=201)
async def add_to_watchlist(body: WatchlistAdd, db: Session = Depends(get_db)):
    """Add instrument to watchlist."""
    from core.storage.models import Watchlist
    existing = db.query(Watchlist).filter(Watchlist.instrument_id == body.instrument_id).first()
    if existing:
        existing.is_active = True
        db.commit()
        return {"ok": True, "action": "reactivated"}

    item = Watchlist(
        instrument_id=body.instrument_id,
        ticker=body.ticker,
        name=body.name,
        exchange=body.exchange,
        is_active=True,
        added_ts=int(time.time() * 1000),
    )
    db.add(item)
    db.commit()
    return {"ok": True, "action": "added"}


@router.delete("/{instrument_id}")
async def remove_from_watchlist(instrument_id: str, db: Session = Depends(get_db)):
    """Deactivate instrument in watchlist (soft delete)."""
    from core.storage.models import Watchlist, Position
    # Warn if open position
    has_position = db.query(Position).filter(
        Position.instrument_id == instrument_id, Position.qty > 0
    ).first()
    if has_position:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot remove {instrument_id}: open position exists"
        )
    item = db.query(Watchlist).filter(Watchlist.instrument_id == instrument_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not in watchlist")
    item.is_active = False
    db.commit()
    return {"ok": True}
