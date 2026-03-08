from __future__ import annotations

from typing import Any

import sqlalchemy
from sqlalchemy.orm import Session

from core.config import get_token, settings as config
from core.storage.models import Settings


CANONICAL_TRADE_MODES = {"review", "auto_paper", "auto_live"}
LEGACY_TRADE_MODE_MAP = {
    "paper": "auto_paper",
    "live": "auto_live",
    "auto_live": "auto_live",
    "review": "review",
    "auto_paper": "auto_paper",
}


def normalize_trade_mode(value: str | None) -> str:
    if not value:
        return "review"
    return LEGACY_TRADE_MODE_MAP.get(value, "review")


def live_capable() -> bool:
    return (
        config.BROKER_PROVIDER == "tbank"
        and bool(get_token("TBANK_TOKEN") or config.TBANK_TOKEN)
        and bool(get_token("TBANK_ACCOUNT_ID") or config.TBANK_ACCOUNT_ID)
        and bool(config.LIVE_TRADING_ENABLED)
    )


async def build_bot_status(db: Session) -> dict[str, Any]:
    settings = db.query(Settings).first()
    trade_mode = normalize_trade_mode(getattr(settings, "trade_mode", "review"))
    bot_enabled = bool(getattr(settings, "bot_enabled", False)) if settings else False

    broker_ok = config.BROKER_PROVIDER == "paper" or bool(get_token("TBANK_TOKEN") or config.TBANK_TOKEN)
    market_data = "connected" if broker_ok else "disconnected"
    broker = "connected" if broker_ok else "disconnected"

    active_instrument_id = ""
    try:
        from core.storage.models import Position

        position = (
            db.query(Position.instrument_id)
            .filter(Position.qty > 0)
            .order_by(Position.updated_ts.desc())
            .first()
        )
        if position:
            active_instrument_id = position[0]
    except Exception:
        active_instrument_id = ""

    warnings: list[str] = []
    auto_live_available = live_capable()
    if config.BROKER_PROVIDER == "tbank" and not auto_live_available:
        warnings.append(
            "Auto Live станет доступен только после задания TBANK_TOKEN, TBANK_ACCOUNT_ID и LIVE_TRADING_ENABLED=true."
        )
    if trade_mode == "auto_live" and not auto_live_available:
        warnings.append("Текущий режим auto_live недоступен по конфигурации и должен быть отключён.")

    try:
        db.execute(sqlalchemy.text("SELECT 1"))
    except Exception:
        market_data = "disconnected"
        warnings.append("База данных недоступна.")

    return {
        "is_running": bot_enabled,
        "mode": trade_mode,
        "is_paper": trade_mode != "auto_live" or config.BROKER_PROVIDER == "paper",
        "active_instrument_id": active_instrument_id,
        "connection": {
            "market_data": market_data,
            "broker": broker,
        },
        "session": {
            "market": "MOEX",
            "timezone": "Europe/Moscow",
            "trading_day": "weekday",
        },
        "capabilities": {
            "manual_review": True,
            "auto_paper": True,
            "auto_live": auto_live_available,
        },
        "warnings": warnings,
    }
