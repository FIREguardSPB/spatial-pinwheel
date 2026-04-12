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

from core.config import get_token, settings as cfg
from core.storage.session import get_db
from apps.api.deps import verify_token
from apps.broker.tbank.adapter import normalize_instrument_id
from core.services.symbol_adaptive import ensure_symbol_profiles

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
async def search_instruments(
    q: str = Query("", min_length=0),
    limit: int = Query(50, ge=1, le=500),
):
    """Search instruments with T-Bank live lookup first and static catalog fallback."""
    q_lower = q.lower().strip()
    static_items = _MOEX_CATALOG[:limit] if not q_lower else [
        item for item in _MOEX_CATALOG
        if q_lower in item["ticker"].lower() or q_lower in item["name"].lower()
    ][:limit]

    runtime_tbank_token = get_token("TBANK_TOKEN") or cfg.TBANK_TOKEN
    runtime_tbank_account = get_token("TBANK_ACCOUNT_ID") or cfg.TBANK_ACCOUNT_ID
    if cfg.BROKER_PROVIDER == "tbank" and runtime_tbank_token and q_lower:
        try:
            from apps.broker.tbank import TBankGrpcAdapter

            adapter = TBankGrpcAdapter(
                token=runtime_tbank_token,
                account_id=runtime_tbank_account,
                sandbox=cfg.TBANK_SANDBOX,
            )
            try:
                broker_items = await adapter.search_instruments(q, limit=limit)
            finally:
                await adapter.close()

            merged: list[dict] = []
            seen: set[str] = set()
            for item in broker_items + static_items:
                instrument_id = normalize_instrument_id(item["instrument_id"])
                if instrument_id in seen:
                    continue
                seen.add(instrument_id)
                normalized = dict(item)
                normalized["instrument_id"] = instrument_id
                merged.append(normalized)
                if len(merged) >= limit:
                    break
            return {"items": merged}
        except Exception:
            pass

    return {"items": static_items}


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
                "instrument_id": normalize_instrument_id(w.instrument_id),
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
    normalized_instrument_id = normalize_instrument_id(body.instrument_id)
    existing = db.query(Watchlist).filter(Watchlist.instrument_id == normalized_instrument_id).first()
    if existing:
        existing.is_active = True
        ensure_result = ensure_symbol_profiles(db, [normalized_instrument_id], auto_train=False, source='watchlist_add')
        db.commit()
        return {"ok": True, "action": "reactivated", "symbol_profiles": ensure_result}

    item = Watchlist(
        instrument_id=normalized_instrument_id,
        ticker=body.ticker.upper(),
        name=body.name,
        exchange=(body.exchange or normalized_instrument_id.split(':')[0]).upper(),
        is_active=True,
        added_ts=int(time.time() * 1000),
    )
    db.add(item)
    ensure_result = ensure_symbol_profiles(db, [normalized_instrument_id], auto_train=False, source='watchlist_add')
    db.commit()
    return {"ok": True, "action": "added", "symbol_profiles": ensure_result}


@router.delete("/{instrument_id}")
async def remove_from_watchlist(instrument_id: str, db: Session = Depends(get_db)):
    """Deactivate instrument in watchlist (soft delete)."""
    from core.storage.models import Watchlist, Position
    # Warn if open position
    instrument_id = normalize_instrument_id(instrument_id)
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
