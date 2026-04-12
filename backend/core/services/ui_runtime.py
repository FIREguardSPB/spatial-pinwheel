from __future__ import annotations

import time
from typing import Any

from core.config import settings as cfg
from core.services.runtime_tokens import load_runtime_tokens
from core.services.degrade_policy import build_policy_runtime_payload, build_policy_runtime_payload_ui_safe
from core.ml.runtime import build_ml_runtime_status
from core.storage.models import DecisionLog, Signal, Trade, Watchlist
from core.storage.repos import ai_repo, settings as settings_repo


def _now_ms() -> int:
    return int(time.time() * 1000)


def build_ai_runtime_summary(db, settings_db) -> dict[str, Any]:
    tokens = load_runtime_tokens(db, ['CLAUDE_API_KEY', 'OPENAI_API_KEY', 'DEEPSEEK_API_KEY'])
    primary = (getattr(settings_db, 'ai_primary_provider', None) or 'deepseek').strip().lower()
    fallbacks = [p.strip().lower() for p in (getattr(settings_db, 'ai_fallback_providers', None) or 'deepseek,ollama,skip').split(',') if p.strip()]
    last = None
    try:
        recent = ai_repo.list_decisions(db, limit=1)
        last = recent[0] if recent else None
    except Exception:
        last = None
    return {
        'status': 'ready',
        'enabled': (getattr(settings_db, 'ai_mode', 'off') or 'off') != 'off',
        'ai_mode': getattr(settings_db, 'ai_mode', 'off') or 'off',
        'min_confidence': int(getattr(settings_db, 'ai_min_confidence', 55) or 55),
        'primary_provider': primary,
        'fallback_providers': fallbacks,
        'provider_availability': {
            'claude': bool(tokens.get('CLAUDE_API_KEY')),
            'openai': bool(tokens.get('OPENAI_API_KEY')),
            'deepseek': bool(tokens.get('DEEPSEEK_API_KEY')),
            'ollama': bool(getattr(settings_db, 'ollama_url', None) or cfg.OLLAMA_BASE_URL),
            'skip': True,
        },
        'last_decision': (
            {
                'ts': getattr(last, 'ts', None),
                'instrument_id': getattr(last, 'instrument_id', None),
                'provider': getattr(last, 'provider', None),
                'ai_decision': getattr(last, 'ai_decision', None),
                'final_decision': getattr(last, 'final_decision', None),
                'ai_confidence': getattr(last, 'ai_confidence', None),
            }
            if last else None
        ),
    }


def build_telegram_runtime_summary(db, settings_db) -> dict[str, Any]:
    tokens = load_runtime_tokens(db, ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'])
    token = tokens.get('TELEGRAM_BOT_TOKEN') or getattr(settings_db, 'telegram_bot_token', '') or ''
    chat_id = tokens.get('TELEGRAM_CHAT_ID') or getattr(settings_db, 'telegram_chat_id', '') or ''
    return {
        'status': 'ready',
        'configured': bool(token and chat_id),
        'bot_token_present': bool(token),
        'chat_id_present': bool(chat_id),
        'enabled_events': [e.strip() for e in (getattr(settings_db, 'notification_events', '') or '').split(',') if e.strip()],
    }


def build_policy_runtime_summary(db, settings_db) -> dict[str, Any]:
    payload = build_policy_runtime_payload_ui_safe(settings_db)
    payload['has_runtime_decision'] = payload.get('state') not in {'unknown', 'disabled'}
    return payload


def build_ml_runtime_summary(db, settings_db) -> dict[str, Any]:
    payload = build_ml_runtime_status(db, settings_db)
    active_models = payload.get('active_models') or {}
    normalized_models: dict[str, Any] = {}
    ready = False
    for target in ('trade_outcome', 'take_fill'):
        row = active_models.get(target)
        if row:
            ready = True
            normalized_models[target] = {**row, 'status': 'active'}
        else:
            normalized_models[target] = {
                'status': 'missing',
                'reason': 'active model is not trained yet',
            }
    payload['active_models'] = normalized_models
    payload['status'] = 'ready' if ready else 'idle'
    payload['reason'] = None if ready else 'no active trained models yet'
    return payload


def build_pipeline_counters_summary(db, lookback_hours: int = 24) -> dict[str, Any]:
    cutoff = _now_ms() - int(max(1, lookback_hours)) * 60 * 60 * 1000
    try:
        created = db.query(Signal).filter(Signal.created_ts >= cutoff).count()
        take = db.query(Signal).filter(Signal.created_ts >= cutoff, Signal.status.in_(['executed', 'filled', 'closed', 'approved'])).count()
        execution_error = db.query(Signal).filter(Signal.created_ts >= cutoff, Signal.status == 'execution_error').count()
        risk_block = db.query(DecisionLog).filter(DecisionLog.ts >= cutoff, DecisionLog.type == 'signal_risk_block').count()
        filled = db.query(Trade).filter(Trade.ts >= cutoff).count()
        return {
            'status': 'ready',
            'lookback_hours': int(lookback_hours),
            'signals_created': created,
            'signals_progressed': take,
            'trade_fills': filled,
            'risk_blocks': risk_block,
            'execution_errors': execution_error,
        }
    except Exception:
        return {
            'status': 'error',
            'lookback_hours': int(lookback_hours),
            'signals_created': 0,
            'signals_progressed': 0,
            'trade_fills': 0,
            'risk_blocks': 0,
            'execution_errors': 0,
        }


def get_watchlist_items(db) -> list[dict[str, Any]]:
    items = (
        db.query(Watchlist)
        .filter(Watchlist.is_active == True)  # noqa: E712
        .order_by(Watchlist.added_ts)
        .all()
    )
    return [
        {
            'instrument_id': str(w.instrument_id),
            'ticker': str(w.ticker),
            'name': str(w.name),
            'exchange': str(w.exchange or ''),
            'is_active': bool(w.is_active),
            'added_ts': int(w.added_ts or 0),
        }
        for w in items
    ]


def build_settings_runtime_snapshot(db) -> dict[str, Any]:
    settings_db = settings_repo.get_settings(db)
    from apps.api.status import build_bot_status_sync
    from core.services.trading_schedule import get_schedule_snapshot

    schedule = get_schedule_snapshot(session_type=getattr(settings_db, 'trading_session', 'all'))
    return {
        'bot_status': build_bot_status_sync(db),
        'settings': settings_db,
        'schedule': schedule,
        'watchlist': get_watchlist_items(db),
        'ai_runtime': build_ai_runtime_summary(db, settings_db),
        'telegram': build_telegram_runtime_summary(db, settings_db),
        'auto_policy': build_policy_runtime_summary(db, settings_db),
        'ml_runtime': build_ml_runtime_summary(db, settings_db),
        'pipeline_counters': build_pipeline_counters_summary(db, 24),
    }
