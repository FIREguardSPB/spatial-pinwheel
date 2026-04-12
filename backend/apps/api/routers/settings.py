from __future__ import annotations

import time
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from core.storage.session import SessionLocal, get_db
from core.storage.repos import settings as repo
from core.storage.repos import ai_repo
from core.models import schemas
from core.config import get_token, settings as cfg
from apps.api.deps import verify_token
from apps.api.status import normalize_trade_mode
from core.notifications.telegram import TelegramNotifier
from core.services.symbol_adaptive import build_symbol_plan_readonly, get_symbol_diagnostics, get_symbol_profile
from core.services.trading_schedule import refresh_trading_schedule, get_schedule_snapshot
from core.services.worker_status import read_worker_status
from core.services.degrade_policy import build_policy_runtime_payload_ui_safe
from core.ml.runtime import build_ml_runtime_status
from collections import Counter
from typing import Any
from core.storage.models import CandleCache, SymbolEventRegime, DecisionLog

router = APIRouter(dependencies=[Depends(verify_token)])


def _with_runtime_session(fn, *args, **kwargs):
    db = SessionLocal()
    try:
        return fn(db, *args, **kwargs)
    finally:
        db.close()

SAFE_GLOBAL_FIELDS = [
    'risk_per_trade_pct',
    'daily_loss_limit_pct',
    'max_concurrent_positions',
    'max_trades_per_day',
    'max_position_notional_pct_balance',
    'max_total_exposure_pct_balance',
    'trade_mode',
    'use_broker_trading_schedule',
    'trading_session',
    'worker_bootstrap_limit',
]

CAUTION_FIELDS = [
    'decision_threshold',
    'time_stop_bars',
    'signal_reentry_cooldown_sec',
    'pending_review_ttl_sec',
    'max_pending_per_symbol',
    'rr_min',
    'rr_target',
    'fees_bps',
    'slippage_bps',
    'min_sl_distance_pct',
    'min_profit_after_costs_multiplier',
    'min_tick_floor_rub',
    'volatility_sl_floor_multiplier',
    'sl_cost_floor_multiplier',
    'w_regime',
    'w_volatility',
    'w_momentum',
    'w_levels',
    'w_costs',
    'w_liquidity',
    'w_volume',
    'ai_mode',
    'ai_primary_provider',
    'ai_fallback_providers',
    'ai_min_confidence',
    'auto_policy_lookback_days',
    'auto_degrade_max_execution_errors',
    'auto_freeze_max_execution_errors',
    'auto_degrade_min_profit_factor',
    'auto_freeze_min_profit_factor',
    'auto_degrade_min_expectancy',
    'auto_freeze_min_expectancy',
    'auto_degrade_drawdown_pct',
    'auto_freeze_drawdown_pct',
    'auto_degrade_risk_multiplier',
    'auto_degrade_threshold_penalty',
]

AUTO_OWNED_FIELDS = [
    'effective_strategy',
    'effective_regime',
    'effective_threshold',
    'effective_hold_bars',
    'effective_reentry_cooldown_sec',
    'effective_risk_multiplier',
    'auto_policy_state',
    'auto_policy_reasons',
]


def _num(value, default):
    return float(default) if value is None else float(value)


def _int_value(value, default):
    return int(default) if value is None else int(value)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _settings_to_schema(settings_db) -> schemas.RiskSettings:
    return schemas.RiskSettings(
        id=getattr(settings_db, 'id', None),
        updated_ts=getattr(settings_db, 'updated_ts', None),
        is_active=bool(getattr(settings_db, 'is_active', False)),
        risk_profile=settings_db.risk_profile,
        risk_per_trade_pct=settings_db.risk_per_trade_pct,
        daily_loss_limit_pct=settings_db.daily_loss_limit_pct,
        max_concurrent_positions=settings_db.max_concurrent_positions,
        max_trades_per_day=settings_db.max_trades_per_day,
        fees_bps=getattr(settings_db, 'fees_bps', 3),
        slippage_bps=getattr(settings_db, 'slippage_bps', 5),
        max_position_notional_pct_balance=_num(getattr(settings_db, 'max_position_notional_pct_balance', None), 10.0),
        max_total_exposure_pct_balance=_num(getattr(settings_db, 'max_total_exposure_pct_balance', None), 35.0),
        signal_reentry_cooldown_sec=_int_value(getattr(settings_db, 'signal_reentry_cooldown_sec', None), 300),
        pending_review_ttl_sec=_int_value(getattr(settings_db, 'pending_review_ttl_sec', None), 900),
        max_pending_per_symbol=_int_value(getattr(settings_db, 'max_pending_per_symbol', None), 1),
        strong_signal_score_threshold=_int_value(getattr(settings_db, 'strong_signal_score_threshold', None), 80),
        strong_signal_position_bonus=_int_value(getattr(settings_db, 'strong_signal_position_bonus', None), 2),
        partial_close_threshold=_int_value(getattr(settings_db, 'partial_close_threshold', None), 80),
        partial_close_ratio=_num(getattr(settings_db, 'partial_close_ratio', None), 0.5),
        min_position_age_for_partial_close=_int_value(getattr(settings_db, 'min_position_age_for_partial_close', None), 180),
        worker_bootstrap_limit=_int_value(getattr(settings_db, 'worker_bootstrap_limit', None), 10),
        capital_allocator_enabled=bool(getattr(settings_db, 'capital_allocator_enabled', True)),
        capital_allocator_min_score_gap=_int_value(getattr(settings_db, 'capital_allocator_min_score_gap', None), 12),
        capital_allocator_min_free_cash_pct=_num(getattr(settings_db, 'capital_allocator_min_free_cash_pct', None), 8.0),
        capital_allocator_max_reallocation_pct=_num(getattr(settings_db, 'capital_allocator_max_reallocation_pct', None), 0.65),
        capital_allocator_min_edge_improvement=_num(getattr(settings_db, 'capital_allocator_min_edge_improvement', None), 0.18),
        capital_allocator_max_position_concentration_pct=_num(getattr(settings_db, 'capital_allocator_max_position_concentration_pct', None), 18.0),
        capital_allocator_age_decay_per_hour=_num(getattr(settings_db, 'capital_allocator_age_decay_per_hour', None), 0.08),
        symbol_recalibration_enabled=bool(getattr(settings_db, 'symbol_recalibration_enabled', True)),
        symbol_recalibration_hour_msk=_int_value(getattr(settings_db, 'symbol_recalibration_hour_msk', None), 4),
        symbol_recalibration_train_limit=_int_value(getattr(settings_db, 'symbol_recalibration_train_limit', None), 6),
        symbol_recalibration_lookback_days=_int_value(getattr(settings_db, 'symbol_recalibration_lookback_days', None), 180),
        event_regime_enabled=bool(getattr(settings_db, 'event_regime_enabled', True)),
        event_regime_block_severity=_num(getattr(settings_db, 'event_regime_block_severity', None), 0.82),
        adaptive_exit_enabled=bool(getattr(settings_db, 'adaptive_exit_enabled', True)),
        adaptive_exit_extend_bars_limit=_int_value(getattr(settings_db, 'adaptive_exit_extend_bars_limit', None), 8),
        adaptive_exit_tighten_sl_pct=_num(getattr(settings_db, 'adaptive_exit_tighten_sl_pct', None), 0.35),
        adaptive_exit_partial_cooldown_sec=_int_value(getattr(settings_db, 'adaptive_exit_partial_cooldown_sec', None), 180),
        adaptive_exit_max_partial_closes=_int_value(getattr(settings_db, 'adaptive_exit_max_partial_closes', None), 2),
        signal_freshness_enabled=bool(getattr(settings_db, 'signal_freshness_enabled', True)),
        signal_freshness_grace_bars=_num(getattr(settings_db, 'signal_freshness_grace_bars', None), 1.0),
        signal_freshness_penalty_per_bar=_int_value(getattr(settings_db, 'signal_freshness_penalty_per_bar', None), 6),
        signal_freshness_max_bars=_num(getattr(settings_db, 'signal_freshness_max_bars', None), 3.0),
        pm_risk_throttle_enabled=bool(getattr(settings_db, 'pm_risk_throttle_enabled', True)),
        pm_drawdown_soft_limit_pct=_num(getattr(settings_db, 'pm_drawdown_soft_limit_pct', None), 1.5),
        pm_drawdown_hard_limit_pct=_num(getattr(settings_db, 'pm_drawdown_hard_limit_pct', None), 3.0),
        pm_loss_streak_soft_limit=_int_value(getattr(settings_db, 'pm_loss_streak_soft_limit', None), 2),
        pm_loss_streak_hard_limit=_int_value(getattr(settings_db, 'pm_loss_streak_hard_limit', None), 4),
        pm_min_risk_multiplier=_num(getattr(settings_db, 'pm_min_risk_multiplier', None), 0.35),
        auto_degrade_enabled=bool(getattr(settings_db, 'auto_degrade_enabled', True)),
        auto_freeze_enabled=bool(getattr(settings_db, 'auto_freeze_enabled', True)),
        auto_policy_lookback_days=_int_value(getattr(settings_db, 'auto_policy_lookback_days', None), 14),
        auto_degrade_max_execution_errors=_int_value(getattr(settings_db, 'auto_degrade_max_execution_errors', None), 4),
        auto_freeze_max_execution_errors=_int_value(getattr(settings_db, 'auto_freeze_max_execution_errors', None), 10),
        auto_degrade_min_profit_factor=_num(getattr(settings_db, 'auto_degrade_min_profit_factor', None), 0.95),
        auto_freeze_min_profit_factor=_num(getattr(settings_db, 'auto_freeze_min_profit_factor', None), 0.70),
        auto_degrade_min_expectancy=_num(getattr(settings_db, 'auto_degrade_min_expectancy', None), -50.0),
        auto_freeze_min_expectancy=_num(getattr(settings_db, 'auto_freeze_min_expectancy', None), -250.0),
        auto_degrade_drawdown_pct=_num(getattr(settings_db, 'auto_degrade_drawdown_pct', None), 2.5),
        auto_freeze_drawdown_pct=_num(getattr(settings_db, 'auto_freeze_drawdown_pct', None), 5.0),
        auto_degrade_risk_multiplier=_num(getattr(settings_db, 'auto_degrade_risk_multiplier', None), 0.55),
        auto_degrade_threshold_penalty=_int_value(getattr(settings_db, 'auto_degrade_threshold_penalty', None), 8),
        auto_freeze_new_entries=bool(getattr(settings_db, 'auto_freeze_new_entries', True)),
        performance_governor_enabled=bool(getattr(settings_db, 'performance_governor_enabled', True)),
        performance_governor_lookback_days=_int_value(getattr(settings_db, 'performance_governor_lookback_days', None), 45),
        performance_governor_min_closed_trades=_int_value(getattr(settings_db, 'performance_governor_min_closed_trades', None), 3),
        performance_governor_strict_whitelist=bool(getattr(settings_db, 'performance_governor_strict_whitelist', True)),
        performance_governor_auto_suppress=bool(getattr(settings_db, 'performance_governor_auto_suppress', True)),
        performance_governor_max_execution_error_rate=_num(getattr(settings_db, 'performance_governor_max_execution_error_rate', None), 0.35),
        performance_governor_min_take_fill_rate=_num(getattr(settings_db, 'performance_governor_min_take_fill_rate', None), 0.20),
        performance_governor_pass_risk_multiplier=_num(getattr(settings_db, 'performance_governor_pass_risk_multiplier', None), 1.20),
        performance_governor_fail_risk_multiplier=_num(getattr(settings_db, 'performance_governor_fail_risk_multiplier', None), 0.60),
        performance_governor_threshold_bonus=_int_value(getattr(settings_db, 'performance_governor_threshold_bonus', None), 6),
        performance_governor_threshold_penalty=_int_value(getattr(settings_db, 'performance_governor_threshold_penalty', None), 10),
        performance_governor_execution_priority_boost=_num(getattr(settings_db, 'performance_governor_execution_priority_boost', None), 1.20),
        performance_governor_execution_priority_penalty=_num(getattr(settings_db, 'performance_governor_execution_priority_penalty', None), 0.70),
        performance_governor_allocator_boost=_num(getattr(settings_db, 'performance_governor_allocator_boost', None), 1.15),
        performance_governor_allocator_penalty=_num(getattr(settings_db, 'performance_governor_allocator_penalty', None), 0.80),
        ml_enabled=bool(getattr(settings_db, 'ml_enabled', True)),
        ml_retrain_enabled=bool(getattr(settings_db, 'ml_retrain_enabled', True)),
        ml_lookback_days=_int_value(getattr(settings_db, 'ml_lookback_days', None), 120),
        ml_min_training_samples=_int_value(getattr(settings_db, 'ml_min_training_samples', None), 80),
        ml_retrain_interval_hours=_int_value(getattr(settings_db, 'ml_retrain_interval_hours', None), 24),
        ml_retrain_hour_msk=_int_value(getattr(settings_db, 'ml_retrain_hour_msk', None), 4),
        ml_take_probability_threshold=_num(getattr(settings_db, 'ml_take_probability_threshold', None), 0.55),
        ml_fill_probability_threshold=_num(getattr(settings_db, 'ml_fill_probability_threshold', None), 0.45),
        ml_risk_boost_threshold=_num(getattr(settings_db, 'ml_risk_boost_threshold', None), 0.65),
        ml_risk_cut_threshold=_num(getattr(settings_db, 'ml_risk_cut_threshold', None), 0.45),
        ml_pass_risk_multiplier=_num(getattr(settings_db, 'ml_pass_risk_multiplier', None), 1.15),
        ml_fail_risk_multiplier=_num(getattr(settings_db, 'ml_fail_risk_multiplier', None), 0.75),
        ml_threshold_bonus=_int_value(getattr(settings_db, 'ml_threshold_bonus', None), 4),
        ml_threshold_penalty=_int_value(getattr(settings_db, 'ml_threshold_penalty', None), 8),
        ml_execution_priority_boost=_num(getattr(settings_db, 'ml_execution_priority_boost', None), 1.15),
        ml_execution_priority_penalty=_num(getattr(settings_db, 'ml_execution_priority_penalty', None), 0.80),
        ml_allocator_boost=_num(getattr(settings_db, 'ml_allocator_boost', None), 1.10),
        ml_allocator_penalty=_num(getattr(settings_db, 'ml_allocator_penalty', None), 0.85),
        ml_allow_take_veto=bool(getattr(settings_db, 'ml_allow_take_veto', True)),
        rr_target=settings_db.rr_target,
        time_stop_bars=settings_db.time_stop_bars,
        close_before_session_end_minutes=settings_db.close_before_session_end_minutes,
        cooldown_after_losses={
            "losses": settings_db.cooldown_losses or 2,
            "minutes": settings_db.cooldown_minutes or 60,
        },
        atr_stop_hard_min=settings_db.atr_stop_hard_min,
        atr_stop_hard_max=settings_db.atr_stop_hard_max,
        atr_stop_soft_min=settings_db.atr_stop_soft_min,
        atr_stop_soft_max=settings_db.atr_stop_soft_max,
        rr_min=settings_db.rr_min,
        decision_threshold=settings_db.decision_threshold,
        w_regime=settings_db.w_regime,
        w_volatility=settings_db.w_volatility,
        w_momentum=settings_db.w_momentum,
        w_levels=settings_db.w_levels,
        w_costs=settings_db.w_costs,
        w_liquidity=settings_db.w_liquidity,
        w_volume=getattr(settings_db, 'w_volume', 10),
        strategy_name=getattr(settings_db, 'strategy_name', 'breakout,mean_reversion'),
        ai_mode=getattr(settings_db, 'ai_mode', 'advisory'),
        ai_min_confidence=getattr(settings_db, 'ai_min_confidence', 55),
        ai_primary_provider=getattr(settings_db, 'ai_primary_provider', 'deepseek') or 'deepseek',
        ai_fallback_providers=getattr(settings_db, 'ai_fallback_providers', 'deepseek,ollama,skip') or 'deepseek,ollama,skip',
        ollama_url=getattr(settings_db, 'ollama_url', 'http://localhost:11434') or 'http://localhost:11434',
        ai_override_policy=getattr(settings_db, 'ai_override_policy', 'promote_only') or 'promote_only',
        min_sl_distance_pct=_num(getattr(settings_db, 'min_sl_distance_pct', None), 0.08),
        min_profit_after_costs_multiplier=_num(getattr(settings_db, 'min_profit_after_costs_multiplier', None), 1.25),
        min_trade_value_rub=_num(getattr(settings_db, 'min_trade_value_rub', None), 10.0),
        min_instrument_price_rub=_num(getattr(settings_db, 'min_instrument_price_rub', None), 0.001),
        min_tick_floor_rub=_num(getattr(settings_db, 'min_tick_floor_rub', None), 0.0),
        commission_dominance_warn_ratio=_num(getattr(settings_db, 'commission_dominance_warn_ratio', None), 0.30),
        volatility_sl_floor_multiplier=_num(getattr(settings_db, 'volatility_sl_floor_multiplier', None), 0.0),
        sl_cost_floor_multiplier=_num(getattr(settings_db, 'sl_cost_floor_multiplier', None), 0.0),
        no_trade_opening_minutes=getattr(settings_db, 'no_trade_opening_minutes', 10),
        higher_timeframe=getattr(settings_db, 'higher_timeframe', '15m'),
        trading_session=getattr(settings_db, 'trading_session', 'all') or 'all',
        use_broker_trading_schedule=bool(getattr(settings_db, 'use_broker_trading_schedule', True)),
        trading_schedule_exchange=getattr(settings_db, 'trading_schedule_exchange', '') or '',
        correlation_threshold=_num(getattr(settings_db, 'correlation_threshold', None), 0.8),
        max_correlated_positions=_int_value(getattr(settings_db, 'max_correlated_positions', None), 2),
        telegram_bot_token=getattr(settings_db, 'telegram_bot_token', ''),
        telegram_chat_id=getattr(settings_db, 'telegram_chat_id', ''),
        notification_events=getattr(settings_db, 'notification_events', ''),
        account_balance=_num(getattr(settings_db, 'account_balance', None), 100_000),
        trade_mode=normalize_trade_mode(getattr(settings_db, 'trade_mode', 'review')),
        bot_enabled=bool(getattr(settings_db, 'bot_enabled', False)),
    )


def _ai_runtime_payload(db: Session, settings_db) -> dict:
    primary = (getattr(settings_db, "ai_primary_provider", None) or "deepseek").strip().lower()
    fallbacks = [p.strip().lower() for p in (getattr(settings_db, "ai_fallback_providers", None) or "deepseek,ollama,skip").split(',') if p.strip()]
    chain = [primary, *fallbacks]
    if 'skip' not in chain:
        chain.append('skip')
    available = {
        'claude': bool(get_token('CLAUDE_API_KEY') or cfg.CLAUDE_API_KEY),
        'openai': bool(get_token('OPENAI_API_KEY') or cfg.OPENAI_API_KEY),
        'deepseek': bool(get_token('DEEPSEEK_API_KEY')),
        'ollama': bool(getattr(settings_db, 'ollama_url', None) or cfg.OLLAMA_BASE_URL),
        'skip': True,
    }
    recent = ai_repo.list_decisions(db, limit=10)
    last = recent[0] if recent else None
    return {
        'enabled': (getattr(settings_db, 'ai_mode', 'off') or 'off') != 'off',
        'participates_in_decision': (getattr(settings_db, 'ai_mode', 'off') or 'off') in {'advisory', 'override', 'required'},
        'ai_mode': getattr(settings_db, 'ai_mode', 'off') or 'off',
        'min_confidence': int(getattr(settings_db, 'ai_min_confidence', 55) or 55),
        'override_policy': getattr(settings_db, 'ai_override_policy', 'promote_only') or 'promote_only',
        'primary_provider': primary,
        'fallback_providers': fallbacks,
        'provider_chain': chain,
        'provider_availability': available,
        'ollama_url': getattr(settings_db, 'ollama_url', None) or cfg.OLLAMA_BASE_URL,
        'last_decision': (
            {
                'ts': last.ts,
                'instrument_id': last.instrument_id,
                'provider': last.provider,
                'ai_decision': last.ai_decision,
                'ai_confidence': last.ai_confidence,
                'final_decision': last.final_decision,
                'actual_outcome': last.actual_outcome,
                'latency_ms': last.latency_ms,
            }
            if last else None
        ),
        'recent_count': len(recent),
    }


def _telegram_status_payload(settings_db) -> dict:
    token = get_token('TELEGRAM_BOT_TOKEN') or getattr(settings_db, 'telegram_bot_token', '') or ''
    chat_id = get_token('TELEGRAM_CHAT_ID') or getattr(settings_db, 'telegram_chat_id', '') or ''
    enabled_events = [e.strip() for e in (getattr(settings_db, 'notification_events', '') or '').split(',') if e.strip()]
    quiet_raw = getattr(settings_db, 'no_notification_hours', '') or ''
    quiet_hours = [int(h) for h in quiet_raw.split(',') if h.strip().isdigit()]
    return {
        'configured': bool(token and chat_id),
        'bot_token_present': bool(token),
        'chat_id_present': bool(chat_id),
        'enabled_events': enabled_events,
        'quiet_hours': quiet_hours,
        'transport': 'telegram_bot_api',
    }


def _global_defaults_payload(settings_db) -> dict:
    return {
        'risk_guardrails': {
            'risk_per_trade_pct': float(getattr(settings_db, 'risk_per_trade_pct', 0.0) or 0.0),
            'daily_loss_limit_pct': float(getattr(settings_db, 'daily_loss_limit_pct', 0.0) or 0.0),
            'max_concurrent_positions': int(getattr(settings_db, 'max_concurrent_positions', 0) or 0),
            'max_trades_per_day': int(getattr(settings_db, 'max_trades_per_day', 0) or 0),
            'max_position_notional_pct_balance': _num(getattr(settings_db, 'max_position_notional_pct_balance', None), 10.0),
            'max_total_exposure_pct_balance': _num(getattr(settings_db, 'max_total_exposure_pct_balance', None), 35.0),
            'correlation_threshold': _num(getattr(settings_db, 'correlation_threshold', None), 0.8),
            'max_correlated_positions': _int_value(getattr(settings_db, 'max_correlated_positions', None), 2),
        },
        'base_engine_defaults': {
            'decision_threshold': int(getattr(settings_db, 'decision_threshold', 70) or 70),
            'time_stop_bars': int(getattr(settings_db, 'time_stop_bars', 12) or 12),
            'signal_reentry_cooldown_sec': int(getattr(settings_db, 'signal_reentry_cooldown_sec', 300) or 300),
            'pending_review_ttl_sec': int(getattr(settings_db, 'pending_review_ttl_sec', 900) or 900),
            'max_pending_per_symbol': int(getattr(settings_db, 'max_pending_per_symbol', 1) or 1),
            'rr_min': float(getattr(settings_db, 'rr_min', 0.0) or 0.0),
            'rr_target': float(getattr(settings_db, 'rr_target', 0.0) or 0.0),
            'min_sl_distance_pct': _num(getattr(settings_db, 'min_sl_distance_pct', None), 0.08),
            'min_profit_after_costs_multiplier': _num(getattr(settings_db, 'min_profit_after_costs_multiplier', None), 1.25),
            'fees_bps': float(getattr(settings_db, 'fees_bps', 0.0) or 0.0),
            'slippage_bps': float(getattr(settings_db, 'slippage_bps', 0.0) or 0.0),
            'strategy_name': getattr(settings_db, 'strategy_name', 'breakout,mean_reversion') or 'breakout,mean_reversion',
            'higher_timeframe': getattr(settings_db, 'higher_timeframe', '15m') or '15m',
            'adaptive_exit_partial_cooldown_sec': _int_value(getattr(settings_db, 'adaptive_exit_partial_cooldown_sec', None), 180),
            'adaptive_exit_max_partial_closes': _int_value(getattr(settings_db, 'adaptive_exit_max_partial_closes', None), 2),
            'capital_allocator_min_edge_improvement': _num(getattr(settings_db, 'capital_allocator_min_edge_improvement', None), 0.18),
            'capital_allocator_max_position_concentration_pct': _num(getattr(settings_db, 'capital_allocator_max_position_concentration_pct', None), 18.0),
            'capital_allocator_age_decay_per_hour': _num(getattr(settings_db, 'capital_allocator_age_decay_per_hour', None), 0.08),
            'performance_governor_pass_risk_multiplier': _num(getattr(settings_db, 'performance_governor_pass_risk_multiplier', None), 1.20),
            'performance_governor_fail_risk_multiplier': _num(getattr(settings_db, 'performance_governor_fail_risk_multiplier', None), 0.60),
            'performance_governor_threshold_bonus': _int_value(getattr(settings_db, 'performance_governor_threshold_bonus', None), 6),
            'performance_governor_threshold_penalty': _int_value(getattr(settings_db, 'performance_governor_threshold_penalty', None), 10),
        },
        'automation_switches': {
            'trade_mode': normalize_trade_mode(getattr(settings_db, 'trade_mode', 'review')),
            'ai_mode': getattr(settings_db, 'ai_mode', 'off') or 'off',
            'event_regime_enabled': bool(getattr(settings_db, 'event_regime_enabled', True)),
            'capital_allocator_enabled': bool(getattr(settings_db, 'capital_allocator_enabled', True)),
            'adaptive_exit_enabled': bool(getattr(settings_db, 'adaptive_exit_enabled', True)),
            'performance_governor_enabled': bool(getattr(settings_db, 'performance_governor_enabled', True)),
            'performance_governor_lookback_days': _int_value(getattr(settings_db, 'performance_governor_lookback_days', None), 45),
            'performance_governor_min_closed_trades': _int_value(getattr(settings_db, 'performance_governor_min_closed_trades', None), 3),
            'performance_governor_strict_whitelist': bool(getattr(settings_db, 'performance_governor_strict_whitelist', True)),
            'performance_governor_auto_suppress': bool(getattr(settings_db, 'performance_governor_auto_suppress', True)),
            'symbol_recalibration_enabled': bool(getattr(settings_db, 'symbol_recalibration_enabled', True)),
            'symbol_recalibration_hour_msk': _int_value(getattr(settings_db, 'symbol_recalibration_hour_msk', None), 4),
            'symbol_recalibration_train_limit': _int_value(getattr(settings_db, 'symbol_recalibration_train_limit', None), 6),
            'symbol_recalibration_lookback_days': _int_value(getattr(settings_db, 'symbol_recalibration_lookback_days', None), 180),
            'use_broker_trading_schedule': bool(getattr(settings_db, 'use_broker_trading_schedule', True)),
            'worker_bootstrap_limit': _int_value(getattr(settings_db, 'worker_bootstrap_limit', None), 10),
        },
    }


@router.get("", response_model=schemas.RiskSettings)
def get_settings(db: Session = Depends(get_db)):
    settings_db = repo.get_settings(db)
    return _settings_to_schema(settings_db)


@router.put("", response_model=schemas.RiskSettings)
def update_settings(update_data: schemas.RiskSettings, db: Session = Depends(get_db)):
    settings_db = repo.update_settings(db, update_data)
    return _settings_to_schema(settings_db)


@router.get('/trading-schedule')
async def get_trading_schedule(db: Session = Depends(get_db)):
    settings_db = repo.get_settings(db)
    return get_schedule_snapshot(session_type=getattr(settings_db, 'trading_session', 'all'))


@router.post('/trading-schedule/sync')
async def sync_trading_schedule(db: Session = Depends(get_db)):
    settings_db = repo.get_settings(db)
    if bool(getattr(settings_db, 'use_broker_trading_schedule', True)):
        await refresh_trading_schedule(
            exchange=(getattr(settings_db, 'trading_schedule_exchange', None) or None),
            force=True,
        )
    return get_schedule_snapshot(session_type=getattr(settings_db, 'trading_session', 'all'))


def _runtime_overview_sync(db: Session, instrument_id: str | None, include_globals: bool) -> dict[str, Any]:
    settings_db = repo.get_settings(db)
    profile = None
    current_plan = None
    diagnostics = None
    event_regime = None
    source_notes: list[str] = []

    def _safe_error_payload(exc: Exception) -> dict[str, Any]:
        return {'status': 'error', 'message': str(exc)}

    if instrument_id:
        try:
            profile = get_symbol_profile(instrument_id, db=db)
        except Exception as exc:
            profile = _safe_error_payload(exc)
            source_notes.append('symbol profile failed')
        try:
            diagnostics = get_symbol_diagnostics(db, instrument_id)
        except Exception as exc:
            diagnostics = _safe_error_payload(exc)
            source_notes.append('symbol diagnostics failed')
        candles = (
            db.query(CandleCache)
            .filter(CandleCache.instrument_id == instrument_id, CandleCache.timeframe == '1m')
            .order_by(CandleCache.ts.desc())
            .limit(120)
            .all()
        )
        history = [
            {
                'time': int(c.ts),
                'open': float(c.open),
                'high': float(c.high),
                'low': float(c.low),
                'close': float(c.close),
                'volume': int(c.volume or 0),
            }
            for c in reversed(candles)
        ]
        if history:
            try:
                current_plan = build_symbol_plan_readonly(db, instrument_id, history, settings_db).to_meta()
                source_notes.append('effective plan built from symbol profile + recent candle history + event regime + global defaults')
            except Exception as exc:
                current_plan = _safe_error_payload(exc)
                source_notes.append('effective plan build failed')
        else:
            current_plan = {'status': 'empty', 'message': 'no recent candle history found'}
            source_notes.append('no recent candle history found, effective plan unavailable')
        try:
            row = (
                db.query(SymbolEventRegime)
                .filter(SymbolEventRegime.instrument_id == instrument_id)
                .order_by(SymbolEventRegime.ts.desc())
                .first()
            )
            if row:
                event_regime = {
                    'regime': row.regime,
                    'severity': float(row.severity or 0.0),
                    'direction': row.direction,
                    'score_bias': int(row.score_bias or 0),
                    'hold_bias': int(row.hold_bias or 0),
                    'risk_bias': float(row.risk_bias or 1.0),
                    'action': row.action or 'observe',
                    'payload': row.payload or {},
                    'ts': int(row.ts or 0),
                }
            else:
                event_regime = {'status': 'empty', 'message': 'no event regime for instrument'}
        except Exception as exc:
            event_regime = _safe_error_payload(exc)
            source_notes.append('event regime load failed')

    payload = {
        'instrument_id': instrument_id,
        'hierarchy': [
            {
                'title': 'Global risk contour',
                'scope': 'global_guardrails',
                'recommended_to_change': True,
                'description': 'Общие лимиты риска и экспозиции. Действуют на весь счёт и все бумаги.',
                'fields': SAFE_GLOBAL_FIELDS,
            },
            {
                'title': 'Base engine defaults',
                'scope': 'global_defaults',
                'recommended_to_change': 'careful',
                'description': 'Стартовые значения движка. Они не обязаны быть итоговыми для каждой бумаги: adaptive engine может их сместить.',
                'fields': CAUTION_FIELDS,
            },
            {
                'title': 'Per-symbol adaptive plan',
                'scope': 'effective_runtime',
                'recommended_to_change': False,
                'description': 'Итоговые активные параметры по конкретной бумаге. Их рассчитывает бот автоматически на основе профиля, режима и истории.',
                'fields': AUTO_OWNED_FIELDS,
            },
        ],
        'safe_manual_fields': SAFE_GLOBAL_FIELDS,
        'caution_fields': CAUTION_FIELDS,
        'auto_owned_fields': AUTO_OWNED_FIELDS,
        'global_defaults': _global_defaults_payload(settings_db),
        'symbol_profile': profile if profile is not None else {'status': 'empty', 'message': 'symbol profile unavailable'},
        'effective_plan': current_plan if current_plan is not None else {'status': 'empty', 'message': 'effective plan unavailable'},
        'diagnostics': diagnostics if diagnostics is not None else {'status': 'empty', 'message': 'diagnostics unavailable'},
        'event_regime': event_regime if event_regime is not None else {'status': 'empty', 'message': 'event regime unavailable'},
        'source_notes': source_notes,
        'pipeline_counters': _pipeline_counters(db, _now_ms() - 24 * 60 * 60 * 1000) if include_globals else None,
        'ai_runtime': _ai_runtime_payload(db, settings_db) if include_globals else None,
        'telegram': _telegram_status_payload(settings_db) if include_globals else None,
        'auto_policy': build_policy_runtime_payload_ui_safe(settings_db) if include_globals else None,
        'ml_runtime': build_ml_runtime_status(db, settings_db) if include_globals else None,
    }
    return payload


@router.get('/runtime-overview')
async def runtime_overview(
    instrument_id: str | None = Query(default=None),
    include_globals: bool = Query(default=False),
):
    payload = await run_in_threadpool(_with_runtime_session, _runtime_overview_sync, instrument_id, include_globals)
    payload['worker'] = await read_worker_status()
    return payload


@router.post('/telegram/test-send')
async def test_send_telegram(
    body: dict | None = None,
    db: Session = Depends(get_db),
):
    settings_db = repo.get_settings(db)
    notifier = TelegramNotifier.from_settings(settings_db)
    if not notifier:
        raise HTTPException(status_code=400, detail='Telegram bot token or chat id is missing')
    custom_text = str((body or {}).get('message') or '').strip()
    text = custom_text or '🧪 Spatial Pinwheel: тестовое сообщение из панели настроек. Если ты видишь это сообщение, Telegram-канал уведомлений работает.'
    ok = await notifier._send(text)
    return {
        'ok': bool(ok),
        'message': 'Тестовое сообщение отправлено' if ok else 'Не удалось отправить тестовое сообщение в Telegram',
        'telegram': _telegram_status_payload(settings_db),
    }

def _pipeline_counters(db: Session, lookback_ms: int) -> dict[str, Any]:
    rows = (
        db.query(DecisionLog)
        .filter(DecisionLog.ts >= lookback_ms, DecisionLog.type.in_(['signal_risk_block', 'execution_intent', 'trade_filled']))
        .order_by(DecisionLog.ts.desc())
        .limit(5000)
        .all()
    )
    blocked_by = Counter()
    counts = {
        'blocked_total': 0,
        'opened_total': 0,
        'take_total': 0,
    }
    for row in rows:
        payload = row.payload or {}
        if row.type == 'signal_risk_block':
            counts['blocked_total'] += 1
            reason = str((payload.get('risk_detail') or {}).get('blocked_by') or payload.get('risk_reason') or 'unknown')
            blocked_by[reason] += 1
        elif row.type == 'execution_intent' and str(payload.get('final_decision') or '') == 'TAKE':
            counts['take_total'] += 1
        elif row.type == 'trade_filled':
            counts['opened_total'] += 1
    counts['blocked_by'] = dict(blocked_by)
    return counts

