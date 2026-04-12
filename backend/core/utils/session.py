"""
Session utilities for MOEX trading hours.

Prefers broker-provided trading calendars when available and falls back to static
MOEX windows otherwise.
"""
from __future__ import annotations

from datetime import datetime, time as dtime, timezone, timedelta
from typing import Iterable, Tuple

from core.services.trading_schedule import get_cached_session_bounds

_MSK_OFFSET = timedelta(hours=3)
MORNING_OPEN = dtime(6, 50)
MORNING_CLOSE = dtime(9, 50)
MAIN_OPEN = dtime(9, 50)
MAIN_CLOSE = dtime(18, 50)
EVENING_OPEN = dtime(19, 0)
EVENING_CLOSE = dtime(23, 50)

MOEX_OPEN = MAIN_OPEN
MOEX_CLOSE = MAIN_CLOSE


def _msk_now() -> datetime:
    return datetime.now(timezone.utc) + _MSK_OFFSET


def normalize_session_type(session_type: str | None) -> str:
    raw = (session_type or 'all').strip().lower()
    aliases = {
        'main': 'main',
        'main_only': 'main_only',
        'main+evening': 'all',
        'all': 'all',
        'full': 'all',
        'morning': 'morning',
        'evening': 'evening',
    }
    return aliases.get(raw, 'all')


def _session_windows(session_type: str | None = 'all') -> tuple[tuple[dtime, dtime], ...]:
    normalized = normalize_session_type(session_type)
    if normalized == 'morning':
        return ((MORNING_OPEN, MORNING_CLOSE),)
    if normalized == 'main_only':
        return ((MAIN_OPEN, MAIN_CLOSE),)
    if normalized == 'evening':
        return ((EVENING_OPEN, EVENING_CLOSE),)
    if normalized == 'main':
        return ((MORNING_OPEN, MAIN_CLOSE),)
    return ((MORNING_OPEN, MAIN_CLOSE),)


def _in_window(now_t: dtime, windows: Iterable[Tuple[dtime, dtime]]) -> bool:
    return any(start <= now_t <= end for start, end in windows)


def _cached_bounds(session_type: str | None = 'all') -> tuple[datetime | None, datetime | None, bool | None]:
    return get_cached_session_bounds(session_type=normalize_session_type(session_type))


def is_trading_session(session_type: str | None = 'all') -> bool:
    start_dt, end_dt, is_open = _cached_bounds(session_type)
    if start_dt is not None and end_dt is not None and is_open is not None:
        return bool(is_open)
    now_t = _msk_now().time()
    return _in_window(now_t, _session_windows(session_type))


def current_session_bounds(session_type: str | None = 'all') -> tuple[dtime, dtime] | tuple[None, None]:
    start_dt, end_dt, _ = _cached_bounds(session_type)
    if start_dt is not None and end_dt is not None:
        start_msk = start_dt.astimezone(timezone.utc) + _MSK_OFFSET
        end_msk = end_dt.astimezone(timezone.utc) + _MSK_OFFSET
        return start_msk.time(), end_msk.time()
    windows = _session_windows(session_type)
    now_t = _msk_now().time()
    for start, end in windows:
        if start <= now_t <= end:
            return start, end
    return windows[0] if windows else (None, None)


def minutes_until_session_end(session_type: str | None = 'all') -> float:
    now = _msk_now()
    start_dt, end_dt, is_open = _cached_bounds(session_type)
    if start_dt is not None and end_dt is not None and is_open is not None:
        if not is_open:
            return -1.0
        return (end_dt.astimezone(timezone.utc) - now.astimezone(timezone.utc)).total_seconds() / 60.0
    if not is_trading_session(session_type):
        return -1.0
    _start, end = current_session_bounds(session_type)
    if end is None:
        return -1.0
    today_close = now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    return (today_close - now).total_seconds() / 60.0


def should_close_before_session_end(close_before_minutes: int, session_type: str | None = 'all') -> bool:
    if close_before_minutes <= 0:
        return False
    remaining = minutes_until_session_end(session_type)
    return 0 < remaining <= close_before_minutes
