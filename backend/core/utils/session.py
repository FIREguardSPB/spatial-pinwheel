"""
P2-07: Session utilities — торговые часы MOEX + проверка close_before_session_end.
P2-08: AccountSnapshot model для equity curve (добавляется в models.py отдельно).
"""
from datetime import datetime, time as dtime, timezone, timedelta


# ── MOEX trading session (Moscow time = UTC+3) ────────────────────────────────
MOEX_OPEN  = dtime(9, 50)    # 09:50 МСК
MOEX_CLOSE = dtime(18, 50)   # 18:50 МСК

_MSK_OFFSET = timedelta(hours=3)


def _msk_now() -> datetime:
    return datetime.now(timezone.utc) + _MSK_OFFSET


def is_trading_session() -> bool:
    """Возвращает True если сейчас идёт основная торговая сессия MOEX."""
    now = _msk_now().time()
    return MOEX_OPEN <= now <= MOEX_CLOSE


def minutes_until_session_end() -> float:
    """Минут до закрытия торговой сессии. Отрицательное — сессия закрыта."""
    now = _msk_now()
    today_close = now.replace(
        hour=MOEX_CLOSE.hour, minute=MOEX_CLOSE.minute, second=0, microsecond=0
    )
    delta = (today_close - now).total_seconds() / 60.0
    return delta


def should_close_before_session_end(close_before_minutes: int) -> bool:
    """
    Возвращает True если до закрытия сессии осталось меньше close_before_minutes минут.
    Используется в Worker для принудительного закрытия позиций.
    """
    if close_before_minutes <= 0:
        return False
    remaining = minutes_until_session_end()
    return 0 < remaining <= close_before_minutes
