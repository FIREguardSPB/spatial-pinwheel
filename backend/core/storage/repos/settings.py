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

    db.commit()
    db.refresh(settings)
    return settings
