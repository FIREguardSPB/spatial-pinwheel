from __future__ import annotations

from typing import Any

import sqlalchemy
from sqlalchemy.orm import Session

from core.config import settings as config
from core.services.trading_schedule import get_schedule_snapshot
from core.storage.repos import settings as settings_repo
from core.services.runtime_tokens import load_runtime_tokens

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


def _runtime_transport(settings, token_map: dict[str, str]) -> tuple[str, bool, bool]:
    trade_mode = normalize_trade_mode(getattr(settings, "trade_mode", "review"))
    has_tbank = bool(token_map.get("TBANK_TOKEN")) and bool(token_map.get("TBANK_ACCOUNT_ID"))
    live_available = bool(config.BROKER_PROVIDER == "tbank" and has_tbank and bool(config.LIVE_TRADING_ENABLED))
    effective_provider = "tbank" if trade_mode == "auto_live" and live_available else "paper"
    return effective_provider, has_tbank, live_available


def live_capable_for(settings, token_map: dict[str, str]) -> bool:
    _, _, live_available = _runtime_transport(settings, token_map)
    return live_available


def live_capable() -> bool:
    return (
        config.BROKER_PROVIDER == "tbank"
        and bool(config.TBANK_TOKEN)
        and bool(config.TBANK_ACCOUNT_ID)
        and bool(config.LIVE_TRADING_ENABLED)
    )


def build_bot_status_sync(db: Session) -> dict[str, Any]:
    settings = settings_repo.get_settings(db)
    token_map = load_runtime_tokens(db, ["TBANK_TOKEN", "TBANK_ACCOUNT_ID"])
    trade_mode = normalize_trade_mode(getattr(settings, "trade_mode", "review"))
    bot_enabled = bool(getattr(settings, "bot_enabled", False)) if settings else False

    effective_provider, has_tbank, auto_live_available = _runtime_transport(settings, token_map)
    broker_ok = effective_provider == "paper" or has_tbank
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

    schedule = get_schedule_snapshot(session_type=getattr(settings, 'trading_session', 'all'))
    if schedule.get('source') == 'static':
        warnings.append('Используется fallback-расписание торгов. Подтяни TBANK_TOKEN или нажми синхронизацию расписания.')
    if schedule.get('is_trading_day') is False:
        warnings.append('Сегодня нет торгов по календарю брокера.')

    return {
        "is_running": bot_enabled,
        "mode": trade_mode,
        "is_paper": effective_provider != "tbank",
        "active_instrument_id": active_instrument_id,
        "connection": {
            "market_data": market_data,
            "broker": broker,
            "provider": effective_provider,
        },
        "session": {
            "market": schedule.get('exchange') or 'MOEX',
            "timezone": "Europe/Moscow",
            "trading_day": schedule.get('trading_day') or 'unknown',
            "source": schedule.get('source') or 'static',
            "is_open": schedule.get('is_open'),
            "current_session_start": schedule.get('current_session_start'),
            "current_session_end": schedule.get('current_session_end'),
            "next_open": schedule.get('next_open'),
        },
        "capabilities": {
            "manual_review": True,
            "auto_paper": True,
            "auto_live": auto_live_available,
        },
        "warnings": warnings,
    }


async def build_bot_status(db: Session) -> dict[str, Any]:
    return build_bot_status_sync(db)
