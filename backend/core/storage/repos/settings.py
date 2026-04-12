from __future__ import annotations

from sqlalchemy.orm import Session

from core.storage.models import Settings
from core.models import schemas


_LEGACY_TRADE_MODE_MAP = {
    "paper": "auto_paper",
    "live": "auto_live",
    "auto_live": "auto_live",
    "review": "review",
    "auto_paper": "auto_paper",
}


def normalize_trade_mode(value: str | None) -> str:
    if not value:
        return "review"
    return _LEGACY_TRADE_MODE_MAP.get(value, "review")


def _ordered_settings_query(db: Session):
    return (
        db.query(Settings)
        .order_by(Settings.is_active.desc(), Settings.updated_ts.desc(), Settings.id.desc())
    )


def get_settings(db: Session) -> Settings:
    rows = _ordered_settings_query(db).all()
    if not isinstance(rows, (list, tuple)):
        fallback = db.query(Settings).first()
        if fallback is not None:
            return fallback
        rows = []
    if not rows:
        settings = Settings(is_active=True)
        db.add(settings)
        db.commit()
        db.refresh(settings)
        return settings

    active_rows = [row for row in rows if bool(getattr(row, "is_active", False))]
    selected = active_rows[0] if active_rows else rows[0]

    changed = False
    if not bool(getattr(selected, "is_active", False)):
        selected.is_active = True
        changed = True

    for row in rows:
        should_be_active = row.id == selected.id
        if bool(getattr(row, "is_active", False)) != should_be_active:
            row.is_active = should_be_active
            changed = True

    if changed:
        db.commit()
        db.refresh(selected)
    return selected


def update_settings(db: Session, update_data: schemas.RiskSettings) -> Settings:
    settings = get_settings(db)

    settings.risk_profile = update_data.risk_profile
    settings.risk_per_trade_pct = update_data.risk_per_trade_pct
    settings.daily_loss_limit_pct = update_data.daily_loss_limit_pct
    settings.max_concurrent_positions = update_data.max_concurrent_positions
    settings.max_trades_per_day = update_data.max_trades_per_day
    settings.rr_target = update_data.rr_target
    settings.time_stop_bars = update_data.time_stop_bars
    settings.close_before_session_end_minutes = update_data.close_before_session_end_minutes
    settings.cooldown_losses = update_data.cooldown_after_losses.get("losses", 2)
    settings.cooldown_minutes = update_data.cooldown_after_losses.get("minutes", 60)

    if update_data.atr_stop_hard_min is not None:
        settings.atr_stop_hard_min = update_data.atr_stop_hard_min
    if update_data.atr_stop_hard_max is not None:
        settings.atr_stop_hard_max = update_data.atr_stop_hard_max
    if update_data.atr_stop_soft_min is not None:
        settings.atr_stop_soft_min = update_data.atr_stop_soft_min
    if update_data.atr_stop_soft_max is not None:
        settings.atr_stop_soft_max = update_data.atr_stop_soft_max
    if update_data.rr_min is not None:
        settings.rr_min = update_data.rr_min
    if update_data.decision_threshold is not None:
        settings.decision_threshold = update_data.decision_threshold

    if update_data.w_regime is not None:
        settings.w_regime = update_data.w_regime
    if update_data.w_volatility is not None:
        settings.w_volatility = update_data.w_volatility
    if update_data.w_momentum is not None:
        settings.w_momentum = update_data.w_momentum
    if update_data.w_levels is not None:
        settings.w_levels = update_data.w_levels
    if update_data.w_costs is not None:
        settings.w_costs = update_data.w_costs
    if update_data.w_liquidity is not None:
        settings.w_liquidity = update_data.w_liquidity
    if getattr(update_data, 'w_volume', None) is not None:
        settings.w_volume = update_data.w_volume

    if getattr(update_data, 'strategy_name', None) is not None:
        settings.strategy_name = update_data.strategy_name

    if getattr(update_data, 'ai_mode', None) is not None:
        settings.ai_mode = update_data.ai_mode
    if getattr(update_data, 'ai_min_confidence', None) is not None:
        settings.ai_min_confidence = update_data.ai_min_confidence
    if getattr(update_data, 'ai_primary_provider', None) is not None:
        settings.ai_primary_provider = update_data.ai_primary_provider
    if getattr(update_data, 'ai_fallback_providers', None) is not None:
        settings.ai_fallback_providers = update_data.ai_fallback_providers
    if getattr(update_data, 'ollama_url', None) is not None:
        settings.ollama_url = update_data.ollama_url
    if getattr(update_data, 'ai_override_policy', None) is not None:
        settings.ai_override_policy = update_data.ai_override_policy

    if getattr(update_data, 'min_sl_distance_pct', None) is not None:
        settings.min_sl_distance_pct = update_data.min_sl_distance_pct
    if getattr(update_data, 'min_profit_after_costs_multiplier', None) is not None:
        settings.min_profit_after_costs_multiplier = update_data.min_profit_after_costs_multiplier
    if getattr(update_data, 'min_trade_value_rub', None) is not None:
        settings.min_trade_value_rub = update_data.min_trade_value_rub
    if getattr(update_data, 'min_instrument_price_rub', None) is not None:
        settings.min_instrument_price_rub = update_data.min_instrument_price_rub
    if getattr(update_data, 'min_tick_floor_rub', None) is not None:
        settings.min_tick_floor_rub = update_data.min_tick_floor_rub
    if getattr(update_data, 'commission_dominance_warn_ratio', None) is not None:
        settings.commission_dominance_warn_ratio = update_data.commission_dominance_warn_ratio
    if getattr(update_data, 'volatility_sl_floor_multiplier', None) is not None:
        settings.volatility_sl_floor_multiplier = update_data.volatility_sl_floor_multiplier
    if getattr(update_data, 'sl_cost_floor_multiplier', None) is not None:
        settings.sl_cost_floor_multiplier = update_data.sl_cost_floor_multiplier

    if getattr(update_data, 'no_trade_opening_minutes', None) is not None:
        settings.no_trade_opening_minutes = update_data.no_trade_opening_minutes
    if getattr(update_data, 'higher_timeframe', None) is not None:
        settings.higher_timeframe = update_data.higher_timeframe
    if getattr(update_data, 'trading_session', None) is not None:
        settings.trading_session = update_data.trading_session
    if getattr(update_data, 'use_broker_trading_schedule', None) is not None:
        settings.use_broker_trading_schedule = bool(update_data.use_broker_trading_schedule)
    if getattr(update_data, 'trading_schedule_exchange', None) is not None:
        settings.trading_schedule_exchange = update_data.trading_schedule_exchange

    if getattr(update_data, 'correlation_threshold', None) is not None:
        settings.correlation_threshold = update_data.correlation_threshold
    if getattr(update_data, 'max_correlated_positions', None) is not None:
        settings.max_correlated_positions = update_data.max_correlated_positions

    if getattr(update_data, 'telegram_bot_token', None) is not None:
        settings.telegram_bot_token = update_data.telegram_bot_token
    if getattr(update_data, 'telegram_chat_id', None) is not None:
        settings.telegram_chat_id = update_data.telegram_chat_id
    if getattr(update_data, 'notification_events', None) is not None:
        settings.notification_events = update_data.notification_events

    if getattr(update_data, 'account_balance', None) is not None:
        settings.account_balance = update_data.account_balance
    if getattr(update_data, 'trade_mode', None) is not None:
        settings.trade_mode = normalize_trade_mode(update_data.trade_mode)
    if getattr(update_data, 'bot_enabled', None) is not None:
        settings.bot_enabled = bool(update_data.bot_enabled)
    if getattr(update_data, 'fees_bps', None) is not None:
        settings.fees_bps = update_data.fees_bps
    if getattr(update_data, 'slippage_bps', None) is not None:
        settings.slippage_bps = update_data.slippage_bps
    if getattr(update_data, 'max_position_notional_pct_balance', None) is not None:
        settings.max_position_notional_pct_balance = update_data.max_position_notional_pct_balance
    if getattr(update_data, 'max_total_exposure_pct_balance', None) is not None:
        settings.max_total_exposure_pct_balance = update_data.max_total_exposure_pct_balance
    if getattr(update_data, 'signal_reentry_cooldown_sec', None) is not None:
        settings.signal_reentry_cooldown_sec = update_data.signal_reentry_cooldown_sec
    if getattr(update_data, 'pending_review_ttl_sec', None) is not None:
        settings.pending_review_ttl_sec = update_data.pending_review_ttl_sec
    if getattr(update_data, 'max_pending_per_symbol', None) is not None:
        settings.max_pending_per_symbol = update_data.max_pending_per_symbol
    if getattr(update_data, 'strong_signal_score_threshold', None) is not None:
        settings.strong_signal_score_threshold = update_data.strong_signal_score_threshold
    if getattr(update_data, 'strong_signal_position_bonus', None) is not None:
        settings.strong_signal_position_bonus = update_data.strong_signal_position_bonus
    if getattr(update_data, 'partial_close_threshold', None) is not None:
        settings.partial_close_threshold = update_data.partial_close_threshold
    if getattr(update_data, 'partial_close_ratio', None) is not None:
        settings.partial_close_ratio = update_data.partial_close_ratio
    if getattr(update_data, 'min_position_age_for_partial_close', None) is not None:
        settings.min_position_age_for_partial_close = update_data.min_position_age_for_partial_close
    if getattr(update_data, 'worker_bootstrap_limit', None) is not None:
        settings.worker_bootstrap_limit = update_data.worker_bootstrap_limit
    if getattr(update_data, 'capital_allocator_enabled', None) is not None:
        settings.capital_allocator_enabled = bool(update_data.capital_allocator_enabled)
    if getattr(update_data, 'capital_allocator_min_score_gap', None) is not None:
        settings.capital_allocator_min_score_gap = update_data.capital_allocator_min_score_gap
    if getattr(update_data, 'capital_allocator_min_free_cash_pct', None) is not None:
        settings.capital_allocator_min_free_cash_pct = update_data.capital_allocator_min_free_cash_pct
    if getattr(update_data, 'capital_allocator_max_reallocation_pct', None) is not None:
        settings.capital_allocator_max_reallocation_pct = update_data.capital_allocator_max_reallocation_pct
    if getattr(update_data, 'capital_allocator_min_edge_improvement', None) is not None:
        settings.capital_allocator_min_edge_improvement = update_data.capital_allocator_min_edge_improvement
    if getattr(update_data, 'capital_allocator_max_position_concentration_pct', None) is not None:
        settings.capital_allocator_max_position_concentration_pct = update_data.capital_allocator_max_position_concentration_pct
    if getattr(update_data, 'capital_allocator_age_decay_per_hour', None) is not None:
        settings.capital_allocator_age_decay_per_hour = update_data.capital_allocator_age_decay_per_hour
    if getattr(update_data, 'portfolio_optimizer_enabled', None) is not None:
        settings.portfolio_optimizer_enabled = bool(update_data.portfolio_optimizer_enabled)
    if getattr(update_data, 'portfolio_optimizer_lookback_bars', None) is not None:
        settings.portfolio_optimizer_lookback_bars = update_data.portfolio_optimizer_lookback_bars
    if getattr(update_data, 'portfolio_optimizer_min_history_bars', None) is not None:
        settings.portfolio_optimizer_min_history_bars = update_data.portfolio_optimizer_min_history_bars
    if getattr(update_data, 'portfolio_optimizer_max_pair_corr', None) is not None:
        settings.portfolio_optimizer_max_pair_corr = update_data.portfolio_optimizer_max_pair_corr
    if getattr(update_data, 'portfolio_optimizer_regime_risk_off_multiplier', None) is not None:
        settings.portfolio_optimizer_regime_risk_off_multiplier = update_data.portfolio_optimizer_regime_risk_off_multiplier
    if getattr(update_data, 'portfolio_optimizer_target_weight_buffer_pct', None) is not None:
        settings.portfolio_optimizer_target_weight_buffer_pct = update_data.portfolio_optimizer_target_weight_buffer_pct
    if getattr(update_data, 'symbol_recalibration_enabled', None) is not None:
        settings.symbol_recalibration_enabled = bool(update_data.symbol_recalibration_enabled)
    if getattr(update_data, 'symbol_recalibration_hour_msk', None) is not None:
        settings.symbol_recalibration_hour_msk = update_data.symbol_recalibration_hour_msk
    if getattr(update_data, 'symbol_recalibration_train_limit', None) is not None:
        settings.symbol_recalibration_train_limit = update_data.symbol_recalibration_train_limit
    if getattr(update_data, 'symbol_recalibration_lookback_days', None) is not None:
        settings.symbol_recalibration_lookback_days = update_data.symbol_recalibration_lookback_days
    if getattr(update_data, 'event_regime_enabled', None) is not None:
        settings.event_regime_enabled = bool(update_data.event_regime_enabled)
    if getattr(update_data, 'event_regime_block_severity', None) is not None:
        settings.event_regime_block_severity = update_data.event_regime_block_severity
    if getattr(update_data, 'adaptive_exit_enabled', None) is not None:
        settings.adaptive_exit_enabled = bool(update_data.adaptive_exit_enabled)
    if getattr(update_data, 'adaptive_exit_extend_bars_limit', None) is not None:
        settings.adaptive_exit_extend_bars_limit = update_data.adaptive_exit_extend_bars_limit
    if getattr(update_data, 'adaptive_exit_tighten_sl_pct', None) is not None:
        settings.adaptive_exit_tighten_sl_pct = update_data.adaptive_exit_tighten_sl_pct
    if getattr(update_data, 'adaptive_exit_partial_cooldown_sec', None) is not None:
        settings.adaptive_exit_partial_cooldown_sec = update_data.adaptive_exit_partial_cooldown_sec
    if getattr(update_data, 'adaptive_exit_max_partial_closes', None) is not None:
        settings.adaptive_exit_max_partial_closes = update_data.adaptive_exit_max_partial_closes
    if getattr(update_data, 'signal_freshness_enabled', None) is not None:
        settings.signal_freshness_enabled = bool(update_data.signal_freshness_enabled)
    if getattr(update_data, 'signal_freshness_grace_bars', None) is not None:
        settings.signal_freshness_grace_bars = update_data.signal_freshness_grace_bars
    if getattr(update_data, 'signal_freshness_penalty_per_bar', None) is not None:
        settings.signal_freshness_penalty_per_bar = update_data.signal_freshness_penalty_per_bar
    if getattr(update_data, 'signal_freshness_max_bars', None) is not None:
        settings.signal_freshness_max_bars = update_data.signal_freshness_max_bars
    if getattr(update_data, 'pm_risk_throttle_enabled', None) is not None:
        settings.pm_risk_throttle_enabled = bool(update_data.pm_risk_throttle_enabled)
    if getattr(update_data, 'pm_drawdown_soft_limit_pct', None) is not None:
        settings.pm_drawdown_soft_limit_pct = update_data.pm_drawdown_soft_limit_pct
    if getattr(update_data, 'pm_drawdown_hard_limit_pct', None) is not None:
        settings.pm_drawdown_hard_limit_pct = update_data.pm_drawdown_hard_limit_pct
    if getattr(update_data, 'pm_loss_streak_soft_limit', None) is not None:
        settings.pm_loss_streak_soft_limit = update_data.pm_loss_streak_soft_limit
    if getattr(update_data, 'pm_loss_streak_hard_limit', None) is not None:
        settings.pm_loss_streak_hard_limit = update_data.pm_loss_streak_hard_limit
    if getattr(update_data, 'pm_min_risk_multiplier', None) is not None:
        settings.pm_min_risk_multiplier = update_data.pm_min_risk_multiplier
    if getattr(update_data, 'auto_degrade_enabled', None) is not None:
        settings.auto_degrade_enabled = bool(update_data.auto_degrade_enabled)
    if getattr(update_data, 'auto_freeze_enabled', None) is not None:
        settings.auto_freeze_enabled = bool(update_data.auto_freeze_enabled)
    if getattr(update_data, 'auto_policy_lookback_days', None) is not None:
        settings.auto_policy_lookback_days = update_data.auto_policy_lookback_days
    if getattr(update_data, 'auto_degrade_max_execution_errors', None) is not None:
        settings.auto_degrade_max_execution_errors = update_data.auto_degrade_max_execution_errors
    if getattr(update_data, 'auto_freeze_max_execution_errors', None) is not None:
        settings.auto_freeze_max_execution_errors = update_data.auto_freeze_max_execution_errors
    if getattr(update_data, 'auto_degrade_min_profit_factor', None) is not None:
        settings.auto_degrade_min_profit_factor = update_data.auto_degrade_min_profit_factor
    if getattr(update_data, 'auto_freeze_min_profit_factor', None) is not None:
        settings.auto_freeze_min_profit_factor = update_data.auto_freeze_min_profit_factor
    if getattr(update_data, 'auto_degrade_min_expectancy', None) is not None:
        settings.auto_degrade_min_expectancy = update_data.auto_degrade_min_expectancy
    if getattr(update_data, 'auto_freeze_min_expectancy', None) is not None:
        settings.auto_freeze_min_expectancy = update_data.auto_freeze_min_expectancy
    if getattr(update_data, 'auto_degrade_drawdown_pct', None) is not None:
        settings.auto_degrade_drawdown_pct = update_data.auto_degrade_drawdown_pct
    if getattr(update_data, 'auto_freeze_drawdown_pct', None) is not None:
        settings.auto_freeze_drawdown_pct = update_data.auto_freeze_drawdown_pct
    if getattr(update_data, 'auto_degrade_risk_multiplier', None) is not None:
        settings.auto_degrade_risk_multiplier = update_data.auto_degrade_risk_multiplier
    if getattr(update_data, 'auto_degrade_threshold_penalty', None) is not None:
        settings.auto_degrade_threshold_penalty = update_data.auto_degrade_threshold_penalty
    if getattr(update_data, 'auto_freeze_new_entries', None) is not None:
        settings.auto_freeze_new_entries = bool(update_data.auto_freeze_new_entries)
    if getattr(update_data, 'performance_governor_enabled', None) is not None:
        settings.performance_governor_enabled = bool(update_data.performance_governor_enabled)
    if getattr(update_data, 'performance_governor_lookback_days', None) is not None:
        settings.performance_governor_lookback_days = update_data.performance_governor_lookback_days
    if getattr(update_data, 'performance_governor_min_closed_trades', None) is not None:
        settings.performance_governor_min_closed_trades = update_data.performance_governor_min_closed_trades
    if getattr(update_data, 'performance_governor_strict_whitelist', None) is not None:
        settings.performance_governor_strict_whitelist = bool(update_data.performance_governor_strict_whitelist)
    if getattr(update_data, 'performance_governor_auto_suppress', None) is not None:
        settings.performance_governor_auto_suppress = bool(update_data.performance_governor_auto_suppress)
    if getattr(update_data, 'performance_governor_max_execution_error_rate', None) is not None:
        settings.performance_governor_max_execution_error_rate = update_data.performance_governor_max_execution_error_rate
    if getattr(update_data, 'performance_governor_min_take_fill_rate', None) is not None:
        settings.performance_governor_min_take_fill_rate = update_data.performance_governor_min_take_fill_rate
    if getattr(update_data, 'performance_governor_pass_risk_multiplier', None) is not None:
        settings.performance_governor_pass_risk_multiplier = update_data.performance_governor_pass_risk_multiplier
    if getattr(update_data, 'performance_governor_fail_risk_multiplier', None) is not None:
        settings.performance_governor_fail_risk_multiplier = update_data.performance_governor_fail_risk_multiplier
    if getattr(update_data, 'performance_governor_threshold_bonus', None) is not None:
        settings.performance_governor_threshold_bonus = update_data.performance_governor_threshold_bonus
    if getattr(update_data, 'performance_governor_threshold_penalty', None) is not None:
        settings.performance_governor_threshold_penalty = update_data.performance_governor_threshold_penalty
    if getattr(update_data, 'performance_governor_execution_priority_boost', None) is not None:
        settings.performance_governor_execution_priority_boost = update_data.performance_governor_execution_priority_boost
    if getattr(update_data, 'performance_governor_execution_priority_penalty', None) is not None:
        settings.performance_governor_execution_priority_penalty = update_data.performance_governor_execution_priority_penalty
    if getattr(update_data, 'performance_governor_allocator_boost', None) is not None:
        settings.performance_governor_allocator_boost = update_data.performance_governor_allocator_boost
    if getattr(update_data, 'performance_governor_allocator_penalty', None) is not None:
        settings.performance_governor_allocator_penalty = update_data.performance_governor_allocator_penalty

    settings.is_active = True
    db.commit()
    db.refresh(settings)
    return settings
