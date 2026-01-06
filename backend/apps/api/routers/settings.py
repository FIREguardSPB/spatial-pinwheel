from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.storage.session import get_db
from core.storage.repos import settings as repo
from core.models import schemas

router = APIRouter()


@router.get("", response_model=schemas.RiskSettings)
def get_settings(db: Session = Depends(get_db)):
    settings_db = repo.get_settings(db)
    # Convert DB model to Schema (handling nested cooldown manually if needed, or relying on ORM mode)
    # The Pydantic schema expects a dict for cooldown_after_losses, but DB has separate cols.
    # We construct the response object manually to be safe.
    return schemas.RiskSettings(
        risk_profile=settings_db.risk_profile,
        risk_per_trade_pct=settings_db.risk_per_trade_pct,
        daily_loss_limit_pct=settings_db.daily_loss_limit_pct,
        max_concurrent_positions=settings_db.max_concurrent_positions,
        max_trades_per_day=settings_db.max_trades_per_day,
        rr_target=settings_db.rr_target,
        time_stop_bars=settings_db.time_stop_bars,
        close_before_session_end_minutes=settings_db.close_before_session_end_minutes,
        cooldown_after_losses={
            "losses": settings_db.cooldown_losses,
            "minutes": settings_db.cooldown_minutes,
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
    )


@router.put("", response_model=schemas.RiskSettings)
def update_settings(update_data: schemas.RiskSettings, db: Session = Depends(get_db)):
    settings_db = repo.update_settings(db, update_data)
    return schemas.RiskSettings(
        risk_profile=settings_db.risk_profile,
        risk_per_trade_pct=settings_db.risk_per_trade_pct,
        daily_loss_limit_pct=settings_db.daily_loss_limit_pct,
        max_concurrent_positions=settings_db.max_concurrent_positions,
        max_trades_per_day=settings_db.max_trades_per_day,
        rr_target=settings_db.rr_target,
        time_stop_bars=settings_db.time_stop_bars,
        close_before_session_end_minutes=settings_db.close_before_session_end_minutes,
        cooldown_after_losses={
            "losses": settings_db.cooldown_losses,
            "minutes": settings_db.cooldown_minutes,
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
    )
