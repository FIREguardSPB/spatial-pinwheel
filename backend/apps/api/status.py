from __future__ import annotations

from typing import Any

import sqlalchemy
from sqlalchemy.orm import Session

from core.config import settings as config
from core.services.cognitive_layer import build_cognitive_runtime_summary
from core.execution.anomaly_breaker import evaluate_execution_anomaly_breaker
from core.execution.controls import get_execution_control_snapshot
from core.services.data_edge_runtime import build_data_edge_runtime_summary
from core.services.performance_governor import build_governor_review_runtime_summary, build_slice_review_runtime_summary
from core.services.research_runtime import build_research_runtime_summary
from core.services.trading_schedule import get_schedule_snapshot
from core.services.trade_management_runtime import build_trade_management_runtime_summary
from core.storage.repos import settings as settings_repo
from core.services.runtime_tokens import load_runtime_tokens
from core.services.worker_status import read_worker_status

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
    execution_controls = get_execution_control_snapshot(settings)
    execution_breaker = evaluate_execution_anomaly_breaker(db, settings)
    trade_management = build_trade_management_runtime_summary(db, 24)
    governor_review_calibration = build_governor_review_runtime_summary(db, settings=settings)
    slice_review_calibration = build_slice_review_runtime_summary(db, settings=settings)
    data_edge = build_data_edge_runtime_summary(db, settings)
    cognitive_layer = build_cognitive_runtime_summary(db)
    research_platform = build_research_runtime_summary(db, settings)
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
    if execution_controls.get('blocks_new_entries'):
        warnings.append('Новые входы заблокированы operator execution controls.')
    if execution_controls.get('prefers_paper'):
        warnings.append('Execution принудительно уходит в paper fallback/degraded mode.')
    if execution_breaker.get('action') in {'triggered', 'already_active'} or execution_breaker.get('controls', {}).get('broker_degraded_mode'):
        warnings.append('Execution anomaly breaker активен: новые live entries ограничены до стабилизации исполнения.')
    if governor_review_calibration.get('status') == 'calibrate':
        warnings.append('Review-driven calibration hints active: проверь governor review calibration и trade-management drift.')
    if slice_review_calibration.get('status') == 'calibrate':
        warnings.append('Slice-specific calibration hints active: есть адресные проблемы по strategy/regime slices.')
    if (data_edge.get('market_data') or {}).get('freshness') == 'stale':
        warnings.append('Market data freshness is stale: проверь ingest/polling cadence и feed health.')
    if sum((cognitive_layer.get('contradiction_breakdown') or {}).values()) >= 3:
        warnings.append('Cognitive contradictions accumulating: проверь thesis/scenario alignment on recent signals.')
    if (research_platform.get('challenger_registry') or {}).get('candidate_slices_count', 0) >= 1:
        warnings.append('Research challenger candidates available: можно сравнивать baseline vs challenger по slices.')

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

    worker_status: dict[str, Any] | None = None
    try:
        import asyncio

        worker_status = asyncio.run(read_worker_status())
    except Exception:
        worker_status = None

    worker_ok = bool(worker_status.get('ok')) if isinstance(worker_status, dict) else True
    if bot_enabled and not worker_ok:
        warnings.append('Worker heartbeat is unavailable: бот помечен как запущенный в настройках, но воркер сейчас offline.')

    return {
        "is_running": bool(bot_enabled and worker_ok),
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
        "execution_controls": execution_controls,
        "execution_anomaly_breaker": execution_breaker,
        "trade_management": trade_management,
        "governor_review_calibration": governor_review_calibration,
        "slice_review_calibration": slice_review_calibration,
        "data_edge": data_edge,
        "cognitive_layer": cognitive_layer,
        "research_platform": research_platform,
        "warnings": warnings,
    }


async def build_bot_status(db: Session) -> dict[str, Any]:
    return build_bot_status_sync(db)
