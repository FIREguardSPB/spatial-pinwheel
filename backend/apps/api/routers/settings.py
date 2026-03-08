from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.storage.session import get_db
from core.storage.repos import settings as repo
from core.models import schemas
from apps.api.deps import verify_token
from apps.api.status import normalize_trade_mode

router = APIRouter(dependencies=[Depends(verify_token)])


def _settings_to_schema(settings_db) -> schemas.RiskSettings:
    """Convert ORM Settings model to Pydantic RiskSettings schema (DRY helper)."""
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
        strategy_name=getattr(settings_db, 'strategy_name', 'breakout'),
        # AI
        ai_mode=getattr(settings_db, 'ai_mode', 'off'),
        ai_min_confidence=getattr(settings_db, 'ai_min_confidence', 70),
        ai_primary_provider=getattr(settings_db, 'ai_primary_provider', 'claude') or 'claude',
        ai_fallback_providers=getattr(settings_db, 'ai_fallback_providers', 'deepseek,ollama,skip') or 'deepseek,ollama,skip',
        ollama_url=getattr(settings_db, 'ollama_url', 'http://localhost:11434') or 'http://localhost:11434',
        # Session
        no_trade_opening_minutes=getattr(settings_db, 'no_trade_opening_minutes', 10),
        higher_timeframe=getattr(settings_db, 'higher_timeframe', '15m'),
        # Correlation
        correlation_threshold=float(getattr(settings_db, 'correlation_threshold', 0.8) or 0.8),
        max_correlated_positions=int(getattr(settings_db, 'max_correlated_positions', 2) or 2),
        # Telegram
        telegram_bot_token=getattr(settings_db, 'telegram_bot_token', ''),
        telegram_chat_id=getattr(settings_db, 'telegram_chat_id', ''),
        notification_events=getattr(settings_db, 'notification_events', ''),
        # Account
        account_balance=float(getattr(settings_db, 'account_balance', 100_000) or 100_000),
        trade_mode=normalize_trade_mode(getattr(settings_db, 'trade_mode', 'review')),
        bot_enabled=bool(getattr(settings_db, 'bot_enabled', False)),
    )


@router.get("", response_model=schemas.RiskSettings)
def get_settings(db: Session = Depends(get_db)):
    settings_db = repo.get_settings(db)
    return _settings_to_schema(settings_db)


@router.put("", response_model=schemas.RiskSettings)
def update_settings(update_data: schemas.RiskSettings, db: Session = Depends(get_db)):
    settings_db = repo.update_settings(db, update_data)
    return _settings_to_schema(settings_db)
