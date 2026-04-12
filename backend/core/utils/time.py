"""
P3-04: Утилиты для работы со временем.

Стандарт проекта:
  - В БД: Unix milliseconds (BigInteger)
  - В API: Unix milliseconds
  - Фронтенд делит на 1000 для Date()
  - Lightweight-charts ожидает Unix seconds → фронтенд сам конвертирует
"""
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def now_ms() -> int:
    """Текущее время в Unix milliseconds."""
    return int(time.time() * 1000)


def now_sec() -> int:
    """Текущее время в Unix seconds."""
    return int(time.time())


def sec_to_ms(ts_sec: int | float) -> int:
    """Unix seconds → Unix milliseconds."""
    return int(ts_sec * 1000)


def ms_to_sec(ts_ms: int | float) -> int:
    """Unix milliseconds → Unix seconds."""
    return int(ts_ms / 1000)


def ensure_ms(ts: int | float) -> int:
    """
    Гарантировать milliseconds независимо от входного формата.
    Если ts > 1e10 — уже ms. Если нет — секунды, конвертировать.
    """
    if ts > 10_000_000_000:
        return int(ts)
    return int(ts * 1000)


def ensure_sec(ts: int | float) -> int:
    """
    Гарантировать seconds независимо от входного формата.
    """
    if ts > 10_000_000_000:
        return int(ts / 1000)
    return int(ts)


def from_datetime(dt: datetime) -> int:
    """datetime → Unix ms. Если naive — интерпретируется как UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def to_datetime(ts_ms: int) -> datetime:
    """Unix ms → datetime (UTC)."""
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)


MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def now_msk() -> datetime:
    """Current aware datetime in Europe/Moscow."""
    return datetime.now(MOSCOW_TZ)


def start_of_day_ms(*, tz: ZoneInfo = MOSCOW_TZ, ref: datetime | None = None) -> int:
    """Unix ms for the start of the current trading day in the requested timezone."""
    current = ref.astimezone(tz) if ref is not None else datetime.now(tz)
    sod = current.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(sod.timestamp() * 1000)
