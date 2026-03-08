from apps.api.status import normalize_trade_mode
from sqlalchemy.orm import Session
from core.storage.models import Settings
from core.models import schemas


def get_settings(db: Session) -> Settings:
    settings = db.query(Settings).first()
    if not settings:
        settings = Settings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_settings(db: Session, update_data: schemas.RiskSettings) -> Settings:
    settings = get_settings(db)

    # Simple mapping
    settings.risk_profile = update_data.risk_profile
    settings.risk_per_trade_pct = update_data.risk_per_trade_pct
    settings.daily_loss_limit_pct = update_data.daily_loss_limit_pct
    settings.max_concurrent_positions = update_data.max_concurrent_positions
    settings.max_trades_per_day = update_data.max_trades_per_day
    settings.rr_target = update_data.rr_target
    settings.time_stop_bars = update_data.time_stop_bars
    settings.close_before_session_end_minutes = update_data.close_before_session_end_minutes
    # Handling nested dict by flat key logic if strict, but spec has it flat in DB + fields.
    # We will assume cooldown_losses/minutes map to the dict.
    settings.cooldown_losses = update_data.cooldown_after_losses.get("losses", 2)
    settings.cooldown_minutes = update_data.cooldown_after_losses.get("minutes", 60)

    # Strictness
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

    # Strategy
    if getattr(update_data, 'strategy_name', None) is not None:
        settings.strategy_name = update_data.strategy_name

    # AI settings
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

    # Session (P5-03)
    if getattr(update_data, 'no_trade_opening_minutes', None) is not None:
        settings.no_trade_opening_minutes = update_data.no_trade_opening_minutes
    if getattr(update_data, 'higher_timeframe', None) is not None:
        settings.higher_timeframe = update_data.higher_timeframe

    # Correlation (P5-06)
    if getattr(update_data, 'correlation_threshold', None) is not None:
        settings.correlation_threshold = update_data.correlation_threshold
    if getattr(update_data, 'max_correlated_positions', None) is not None:
        settings.max_correlated_positions = update_data.max_correlated_positions

    # Telegram
    if getattr(update_data, 'telegram_bot_token', None) is not None:
        settings.telegram_bot_token = update_data.telegram_bot_token
    if getattr(update_data, 'telegram_chat_id', None) is not None:
        settings.telegram_chat_id = update_data.telegram_chat_id
    if getattr(update_data, 'notification_events', None) is not None:
        settings.notification_events = update_data.notification_events

    # Account
    if getattr(update_data, 'account_balance', None) is not None:
        settings.account_balance = update_data.account_balance
    if getattr(update_data, 'trade_mode', None) is not None:
        settings.trade_mode = normalize_trade_mode(update_data.trade_mode)
    if getattr(update_data, 'bot_enabled', None) is not None:
        settings.bot_enabled = bool(update_data.bot_enabled)

    db.commit()
    db.refresh(settings)
    return settings
