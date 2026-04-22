from __future__ import annotations

import time
from typing import Any

from core.config import settings as cfg
from core.services.cognitive_layer import build_cognitive_runtime_summary
from core.execution.anomaly_breaker import evaluate_execution_anomaly_breaker
from core.execution.controls import get_execution_control_snapshot
from core.services.data_edge_runtime import build_data_edge_runtime_summary
from core.services.performance_governor import build_governor_review_runtime_summary, build_slice_review_runtime_summary
from core.services.research_runtime import build_research_runtime_summary
from core.services.runtime_tokens import load_runtime_tokens
from core.services.degrade_policy import build_policy_runtime_payload, build_policy_runtime_payload_ui_safe
from core.ml.runtime import build_ml_runtime_status
from core.storage.models import DecisionLog, Signal, Trade, Watchlist
from core.storage.repos import ai_repo, settings as settings_repo
from core.services.sector_filters import enrich_watchlist_items, sector_distribution
from core.services.instrument_catalog import serialize_watchlist_items
from core.sentiment.repo import build_collection_status


def _now_ms() -> int:
    return int(time.time() * 1000)


def build_ai_runtime_summary(db, settings_db) -> dict[str, Any]:
    tokens = load_runtime_tokens(db, ['CLAUDE_API_KEY', 'OPENAI_API_KEY', 'DEEPSEEK_API_KEY'])
    primary = (getattr(settings_db, 'ai_primary_provider', None) or 'deepseek').strip().lower()
    fallbacks = [p.strip().lower() for p in (getattr(settings_db, 'ai_fallback_providers', None) or 'deepseek,ollama,skip').split(',') if p.strip()]
    last = None
    try:
        recent = ai_repo.list_decisions(db, limit=5)
        last = recent[0] if recent else None
    except Exception:
        recent = []
        last = None
    challenger_challenges = 0
    for item in recent or []:
        meta = getattr(item, 'meta', None) or {}
        challenger = meta.get('challenger_agent_shadow') if isinstance(meta, dict) else {}
        if isinstance(challenger, dict) and str(challenger.get('stance') or '') == 'challenge':
            challenger_challenges += 1
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
                'available': True,
                'ts': getattr(last, 'ts', None),
                'instrument_id': getattr(last, 'instrument_id', None),
                'provider': getattr(last, 'provider', None),
                'ai_decision': getattr(last, 'ai_decision', None) or getattr(last, 'decision', None),
                'final_decision': getattr(last, 'final_decision', None),
                'ai_confidence': getattr(last, 'ai_confidence', None) or getattr(last, 'confidence', None),
                'reasoning': getattr(last, 'reasoning', None),
            }
            if last else {'available': False}
        ),
        'agent_shadow': {
            'recent_calls': len(recent or []),
            'challenger_challenges': challenger_challenges,
        },
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
    payload['truth_state'] = 'runtime' if payload['has_runtime_decision'] else 'settings_fallback'
    payload['source'] = 'degrade_policy_runtime' if payload['has_runtime_decision'] else 'ui_safe_fallback'
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


def build_sentiment_runtime_summary(db, settings_db) -> dict[str, Any]:
    payload = build_collection_status(db, settings_db)
    payload['status'] = 'ready'
    return payload


def build_pipeline_counters_summary(db, lookback_hours: int = 24) -> dict[str, Any]:
    cutoff = _now_ms() - int(max(1, lookback_hours)) * 60 * 60 * 1000
    try:
        created = db.query(Signal).filter(Signal.created_ts >= cutoff).count()
        take = db.query(Signal).filter(Signal.created_ts >= cutoff, Signal.status.in_(['executed', 'filled', 'closed', 'approved'])).count()
        pending = db.query(Signal).filter(Signal.created_ts >= cutoff, Signal.status == 'pending_review').count()
        execution_error = db.query(Signal).filter(Signal.created_ts >= cutoff, Signal.status == 'execution_error').count()
        risk_block = db.query(DecisionLog).filter(DecisionLog.ts >= cutoff, DecisionLog.type == 'signal_risk_block').count()
        cooldown_proceed = db.query(DecisionLog).filter(DecisionLog.ts >= cutoff, DecisionLog.type == 'cooldown_aware_proceed').count()
        execution_stage_reject = db.query(DecisionLog).filter(DecisionLog.ts >= cutoff, DecisionLog.type == 'execution_risk_block').count()
        filled = db.query(Trade).filter(Trade.ts >= cutoff).count()
        return {
            'status': 'ready',
            'lookback_hours': int(lookback_hours),
            'signals_created': created,
            'signals_progressed': take,
            'pending_review': pending,
            'progression_rate': round((take / max(1, created)), 4),
            'trade_fills': filled,
            'risk_blocks': risk_block,
            'cooldown_aware_proceeds': cooldown_proceed,
            'execution_stage_rejects': execution_stage_reject,
            'execution_errors': execution_error,
        }
    except Exception:
        return {
            'status': 'error',
            'lookback_hours': int(lookback_hours),
            'signals_created': 0,
            'signals_progressed': 0,
            'pending_review': 0,
            'progression_rate': 0.0,
            'trade_fills': 0,
            'risk_blocks': 0,
            'cooldown_aware_proceeds': 0,
            'execution_stage_rejects': 0,
            'execution_errors': 0,
        }


def get_watchlist_items(db) -> list[dict[str, Any]]:
    return enrich_watchlist_items(serialize_watchlist_items(db))


def build_signal_flow_status(db, lookback_minutes: int = 60) -> dict[str, Any]:
    cutoff = _now_ms() - int(max(1, lookback_minutes)) * 60 * 1000
    try:
        created = db.query(Signal).filter(Signal.created_ts >= cutoff).count()
        progressed = db.query(Signal).filter(Signal.created_ts >= cutoff, Signal.status.in_(['executed', 'filled', 'closed', 'approved'])).count()
        pending = db.query(Signal).filter(Signal.created_ts >= cutoff, Signal.status == 'pending_review').count()
        rejected = db.query(Signal).filter(Signal.created_ts >= cutoff, Signal.status == 'rejected').count()
        execution_rejects = db.query(DecisionLog).filter(DecisionLog.ts >= cutoff, DecisionLog.type == 'execution_risk_block').count()
        cooldown_proceeds = db.query(DecisionLog).filter(DecisionLog.ts >= cutoff, DecisionLog.type == 'cooldown_aware_proceed').count()
        runtime_guards = db.query(DecisionLog).filter(DecisionLog.ts >= cutoff, DecisionLog.type == 'auto_runtime_guard').count()
        degraded = (progressed == 0 and created <= 1) or (created >= 10 and progressed == 0 and rejected >= max(8, int(created * 0.75)))
        suspected = 'healthy'
        if degraded:
            if created >= 10 and progressed == 0 and rejected >= max(8, int(created * 0.75)) and runtime_guards >= max(5, int(created * 0.5)):
                suspected = 'reject_storm_frozen_mode'
            elif runtime_guards > 0:
                suspected = 'frozen_mode_pressure'
            elif cooldown_proceeds > 0:
                suspected = 'cooldown_pressure'
            elif pending > 0 or execution_rejects > 0:
                suspected = 'execution_backlog'
            else:
                suspected = 'no_valid_setups'
        return {
            'status': 'ready',
            'lookback_minutes': int(lookback_minutes),
            'created_last_window': created,
            'progressed_last_window': progressed,
            'pending_review_last_window': pending,
            'rejected_last_window': rejected,
            'degraded_throughput': degraded,
            'suspected_cause': suspected,
        }
    except Exception:
        return {
            'status': 'error',
            'lookback_minutes': int(lookback_minutes),
            'created_last_window': 0,
            'progressed_last_window': 0,
            'pending_review_last_window': 0,
            'rejected_last_window': 0,
            'degraded_throughput': False,
            'suspected_cause': 'runtime_stale',
        }


def build_agent_shadow_runtime_summary(db, lookback_hours: int = 24) -> dict[str, Any]:
    cutoff = _now_ms() - int(max(1, lookback_hours)) * 60 * 60 * 1000
    try:
        rows = (
            db.query(Signal)
            .filter(Signal.created_ts >= cutoff)
            .all()
        )
        consensus_take = 0
        challenger_challenges = 0
        executed_after_consensus_take = 0
        for row in rows:
            meta = dict(getattr(row, 'meta', None) or {})
            merge = dict(meta.get('agent_merge_shadow') or {})
            thesis = dict(meta.get('agent_thesis_shadow') or {})
            if str(merge.get('consensus_action') or '') == 'take':
                consensus_take += 1
                if str(getattr(row, 'status', '') or '') == 'executed':
                    executed_after_consensus_take += 1
            if str(merge.get('challenger_stance') or '') == 'challenge':
                challenger_challenges += 1
        return {
            'status': 'ready',
            'lookback_hours': int(lookback_hours),
            'recent_signals': len(rows),
            'consensus_take': consensus_take,
            'challenger_challenges': challenger_challenges,
            'executed_after_consensus_take': executed_after_consensus_take,
        }
    except Exception:
        return {
            'status': 'error',
            'lookback_hours': int(lookback_hours),
            'recent_signals': 0,
            'consensus_take': 0,
            'challenger_challenges': 0,
            'executed_after_consensus_take': 0,
        }


def build_settings_runtime_snapshot(db) -> dict[str, Any]:
    settings_db = settings_repo.get_settings(db)
    from apps.api.status import build_bot_status_sync
    from core.services.trading_schedule import get_schedule_snapshot
    from core.services.trade_management_runtime import build_trade_management_runtime_summary

    schedule = get_schedule_snapshot(session_type=getattr(settings_db, 'trading_session', 'all'))
    watchlist = get_watchlist_items(db)
    market = {
        'is_open': bool(schedule.get('is_open')),
        'session_type': getattr(settings_db, 'trading_session', 'all') or 'all',
        'source': schedule.get('source'),
        'exchange': schedule.get('exchange'),
        'current_session': schedule.get('current_session'),
        'trading_day': schedule.get('trading_day'),
        'start_at': schedule.get('start_at'),
        'end_at': schedule.get('end_at'),
        'minutes_until_close': schedule.get('minutes_until_close'),
        'warning': schedule.get('warning'),
        'error': schedule.get('error'),
    }
    return {
        'bot_status': build_bot_status_sync(db),
        'settings': settings_db,
        'schedule': schedule,
        'market': market,
        'watchlist': watchlist,
        'watchlist_sector_distribution': sector_distribution(watchlist),
        'ai_runtime': build_ai_runtime_summary(db, settings_db),
        'telegram': build_telegram_runtime_summary(db, settings_db),
        'auto_policy': build_policy_runtime_summary(db, settings_db),
        'execution_controls': get_execution_control_snapshot(settings_db),
        'execution_anomaly_breaker': evaluate_execution_anomaly_breaker(db, settings_db),
        'trade_management': build_trade_management_runtime_summary(db, 24),
        'governor_review_calibration': build_governor_review_runtime_summary(db, settings=settings_db),
        'slice_review_calibration': build_slice_review_runtime_summary(db, settings=settings_db),
        'data_edge': build_data_edge_runtime_summary(db, settings_db),
        'cognitive_layer': build_cognitive_runtime_summary(db),
        'research_platform': build_research_runtime_summary(db, settings_db),
        'ml_runtime': build_ml_runtime_summary(db, settings_db),
        'sentiment_runtime': build_sentiment_runtime_summary(db, settings_db),
        'pipeline_counters': build_pipeline_counters_summary(db, 24),
        'signal_flow': build_signal_flow_status(db, 60),
        'agent_shadow_runtime': build_agent_shadow_runtime_summary(db, 24),
    }
