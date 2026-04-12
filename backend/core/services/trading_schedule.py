from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta, time as dtime, date as ddate
from typing import Any

from core.config import get_token, settings as config

logger = logging.getLogger(__name__)
_MSK = timezone(timedelta(hours=3))
_DEFAULT_TTL_SEC = 60 * 60 * 6
_CACHE: dict[str, Any] = {
    'source': 'static',
    'exchange': None,
    'fetched_at': 0.0,
    'days': {},
    'error': None,
    'warning': None,
}
_LOCK = asyncio.Lock()


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
        except ValueError:
            return None
    if isinstance(value, dict) and 'seconds' in value:
        seconds = int(value.get('seconds') or 0)
        nanos = int(value.get('nanos') or 0)
        return datetime.fromtimestamp(seconds + nanos / 1_000_000_000, tz=timezone.utc)
    return None


_WEEKEND_FALLBACK_START = dtime(9, 50)
_WEEKEND_FALLBACK_END = dtime(18, 59, 59)

# Moscow Exchange official 2026 holiday schedule: all markets are closed on
# 1-4 Jan, 7 Jan, 23 Feb, 8 Mar, 1 May, 9 May, 12 Jun, 4 Nov and 31 Dec 2026;
# on all other days in 2026 the markets operate as usual.
_MOEX_2026_CLOSED_DAYS = {
    '2026-01-01', '2026-01-02', '2026-01-03', '2026-01-04',
    '2026-01-07', '2026-02-23', '2026-03-08', '2026-05-01',
    '2026-05-09', '2026-06-12', '2026-11-04', '2026-12-31',
}
_MOEX_2026_OPEN_EXCEPTIONS = {'2026-01-05', '2026-01-06', '2026-01-08', '2026-01-09', '2026-03-09', '2026-05-11'}


def _dt_to_msk_time(value: datetime | None) -> dtime | None:
    if value is None:
        return None
    return value.astimezone(_MSK).time().replace(tzinfo=None)


def _replace_msk_time_for_date(day_value: str | datetime, value: dtime) -> datetime:
    if isinstance(day_value, str):
        trade_date = ddate.fromisoformat(day_value)
    else:
        trade_date = day_value.astimezone(_MSK).date()
    return datetime.combine(trade_date, value, tzinfo=_MSK).astimezone(timezone.utc)


def _normalize_day(day: dict[str, Any]) -> dict[str, Any]:
    date_utc = _parse_ts(day.get('date'))
    if date_utc is None:
        return {}
    start_time = _parse_ts(day.get('startTime') or day.get('start_time'))
    end_time = _parse_ts(day.get('endTime') or day.get('end_time'))
    evening_start = _parse_ts(day.get('eveningStartTime') or day.get('evening_start_time'))
    evening_end = _parse_ts(day.get('eveningEndTime') or day.get('evening_end_time'))
    opening_auction_start = _parse_ts(day.get('openingAuctionStartTime') or day.get('opening_auction_start_time'))
    opening_auction_end = _parse_ts(day.get('openingAuctionEndTime') or day.get('opening_auction_end_time'))
    premarket_start = _parse_ts(day.get('premarketStartTime') or day.get('premarket_start_time'))
    premarket_end = _parse_ts(day.get('premarketEndTime') or day.get('premarket_end_time'))
    closing_auction_start = _parse_ts(day.get('closingAuctionStartTime') or day.get('closing_auction_start_time'))
    closing_auction_end = _parse_ts(day.get('closingAuctionEndTime') or day.get('closing_auction_end_time'))

    candidates_open = [dt for dt in [premarket_start, opening_auction_start, opening_auction_end, start_time] if dt]
    candidates_close = [dt for dt in [end_time, closing_auction_end, evening_end] if dt]

    return {
        'date': date_utc.astimezone(_MSK).date().isoformat(),
        'is_trading_day': bool(day.get('isTradingDay') if 'isTradingDay' in day else day.get('is_trading_day')),
        'main_start': start_time,
        'main_end': end_time or closing_auction_end or closing_auction_start,
        'opening_auction_start': opening_auction_start,
        'opening_auction_end': opening_auction_end,
        'premarket_start': premarket_start,
        'premarket_end': premarket_end,
        'closing_auction_start': closing_auction_start,
        'closing_auction_end': closing_auction_end,
        'day_start': min(candidates_open) if candidates_open else start_time,
        'day_end': max(candidates_close) if candidates_close else end_time,
        'evening_start': evening_start,
        'evening_end': evening_end,
    }




def _is_weekend_exchange(exchange: str | None) -> bool:
    return 'WEEKEND' in str(exchange or '').upper()


def _normalize_weekend_bounds(day: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    start = day.get('opening_auction_start') or day.get('opening_auction_end') or day.get('main_start') or day.get('day_start')
    end = day.get('main_end') or day.get('closing_auction_end') or day.get('closing_auction_start') or day.get('day_end')
    if start is not None:
        start_msk = _dt_to_msk_time(start)
        if start_msk is not None and start_msk < dtime(6, 0):
            start = _replace_msk_time_for_date(day.get('date') or start, _WEEKEND_FALLBACK_START)
    if end is not None:
        end_msk = _dt_to_msk_time(end)
        if end_msk is not None and end_msk > dtime(20, 0):
            end = _replace_msk_time_for_date(day.get('date') or end, _WEEKEND_FALLBACK_END)
    return start, end

def _select_exchange(payload: dict[str, Any], preferred_exchange: str | None) -> tuple[str | None, list[dict[str, Any]]]:
    exchanges = payload.get('exchanges') or []
    if not exchanges:
        return None, []
    if preferred_exchange:
        for item in exchanges:
            if str(item.get('exchange', '')).upper() == preferred_exchange.upper():
                return item.get('exchange'), item.get('days') or []
    for item in exchanges:
        exchange_name = str(item.get('exchange', ''))
        if 'MOEX' in exchange_name.upper():
            return exchange_name, item.get('days') or []
    first = exchanges[0]
    return first.get('exchange'), first.get('days') or []


async def refresh_trading_schedule(*, exchange: str | None = None, force: bool = False) -> dict[str, Any]:
    now_monotonic = time.monotonic()
    if not force and (_CACHE.get('fetched_at') or 0) and now_monotonic - float(_CACHE['fetched_at']) < _DEFAULT_TTL_SEC:
        return _CACHE

    async with _LOCK:
        if not force and (_CACHE.get('fetched_at') or 0) and now_monotonic - float(_CACHE['fetched_at']) < _DEFAULT_TTL_SEC:
            return _CACHE
        token = get_token('TBANK_TOKEN') or config.TBANK_TOKEN
        if config.BROKER_PROVIDER != 'tbank' or not token:
            _CACHE.update({'source': 'static', 'error': None, 'warning': 'broker schedule unavailable', 'fetched_at': time.monotonic()})
            return _CACHE
        try:
            from apps.broker.tbank import TBankGrpcAdapter
            adapter = TBankGrpcAdapter(
                token=token,
                account_id=get_token('TBANK_ACCOUNT_ID') or config.TBANK_ACCOUNT_ID,
                sandbox=config.TBANK_SANDBOX,
            )
            from_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            to_dt = from_dt + timedelta(days=6)
            payload = await adapter.get_trading_schedules(exchange=exchange, from_dt=from_dt, to_dt=to_dt)
            selected_exchange, days_payload = _select_exchange(payload or {}, exchange)
            normalized_days = {}
            for raw_day in days_payload:
                item = _normalize_day(raw_day)
                if item.get('date'):
                    item['exchange'] = selected_exchange
                    normalized_days[item['date']] = item
            _CACHE.update({
                'source': 'broker',
                'exchange': selected_exchange,
                'days': normalized_days,
                'fetched_at': time.monotonic(),
                'error': None,
            })
            logger.info('Trading schedule refreshed: source=broker exchange=%s days=%d', selected_exchange, len(normalized_days))
        except Exception as exc:
            logger.warning('Trading schedule refresh failed: %s', exc)
            _CACHE.update({'source': 'static', 'error': None, 'warning': str(exc), 'fetched_at': time.monotonic()})
        return _CACHE


def _resolve_bounds(day: dict[str, Any], session_type: str) -> tuple[datetime | None, datetime | None]:
    normalized = (session_type or 'all').strip().lower()
    if _is_weekend_exchange(day.get('exchange')):
        if normalized == 'evening':
            return None, None
        return _normalize_weekend_bounds(day)
    if normalized == 'evening':
        return day.get('evening_start'), day.get('evening_end')
    if normalized == 'main_only':
        return day.get('main_start') or day.get('day_start'), day.get('main_end') or day.get('day_end')
    if normalized in {'main', 'morning'}:
        return day.get('day_start') or day.get('main_start'), day.get('main_end') or day.get('day_end')
    return day.get('day_start') or day.get('main_start'), day.get('evening_end') or day.get('day_end') or day.get('main_end')





def _is_static_moex_trading_day(day_value: ddate) -> bool:
    key = day_value.isoformat()
    if day_value.year == 2026:
        if key in _MOEX_2026_OPEN_EXCEPTIONS:
            return True
        if key in _MOEX_2026_CLOSED_DAYS:
            return False
    return day_value.weekday() < 5


def _next_trading_day_open_after(now_utc: datetime) -> datetime:
    cursor = now_utc.astimezone(_MSK)
    for offset in range(0, 15):
        candidate_date = (cursor + timedelta(days=offset)).date()
        if not _is_static_moex_trading_day(candidate_date):
            continue
        candidate_dt = datetime.combine(candidate_date, _WEEKEND_FALLBACK_START, tzinfo=_MSK).astimezone(timezone.utc)
        if candidate_dt > now_utc:
            return candidate_dt
    fallback_date = (cursor + timedelta(days=1)).date()
    return datetime.combine(fallback_date, _WEEKEND_FALLBACK_START, tzinfo=_MSK).astimezone(timezone.utc)


def _next_weekday_open(now_utc: datetime) -> datetime:
    return _next_trading_day_open_after(now_utc)


def _normalize_snapshot_with_static_guard(snapshot: dict[str, Any], *, now_utc: datetime, session_type: str) -> dict[str, Any]:
    if not snapshot:
        return snapshot
    if (snapshot.get('source') or 'static') == 'static':
        snapshot['error'] = None
        return snapshot
    next_open_raw = snapshot.get('next_open')
    next_open_dt = _parse_ts(next_open_raw)
    if next_open_dt is None:
        return snapshot
    static_snapshot = _static_schedule_snapshot(session_type=session_type, now_utc=now_utc)
    static_next_open = _parse_ts(static_snapshot.get('next_open'))
    if static_next_open is None:
        return snapshot
    gap_hours = (next_open_dt - static_next_open).total_seconds() / 3600.0
    if gap_hours > 24 and _is_static_moex_trading_day(static_next_open.astimezone(_MSK).date()):
        snapshot['next_open'] = static_snapshot.get('next_open')
        snapshot['warning'] = 'broker next_open corrected by static guard'
        snapshot['source_note'] = 'broker schedule sanity override'
    return snapshot


def _static_schedule_snapshot(*, session_type: str, now_utc: datetime) -> dict[str, Any]:
    now_msk = now_utc.astimezone(_MSK)
    today_key = now_msk.date().isoformat()
    is_trading_day = _is_static_moex_trading_day(now_msk.date())
    start_local = datetime.combine(now_msk.date(), _WEEKEND_FALLBACK_START, tzinfo=_MSK)
    end_local = datetime.combine(now_msk.date(), _WEEKEND_FALLBACK_END, tzinfo=_MSK)
    if session_type.strip().lower() == 'evening':
        return {
            'source': 'static',
            'exchange': _CACHE.get('exchange') or 'MOEX',
            'trading_day': today_key,
            'is_trading_day': is_trading_day,
            'is_open': False,
            'current_session_start': None,
            'current_session_end': None,
            'next_open': _next_weekday_open(now_utc).astimezone(_MSK).isoformat(),
            'error': None,
            'warning': _CACHE.get('warning'),
            'fetched_at': _CACHE.get('fetched_at'),
            'timezone': 'Europe/Moscow',
        }
    result = {
        'source': 'static',
        'exchange': _CACHE.get('exchange') or 'MOEX',
        'trading_day': today_key,
        'is_trading_day': is_trading_day,
        'is_open': False,
        'current_session_start': start_local.astimezone(_MSK).isoformat(),
        'current_session_end': end_local.astimezone(_MSK).isoformat(),
        'next_open': None,
        'error': None,
        'warning': _CACHE.get('warning'),
        'fetched_at': _CACHE.get('fetched_at'),
        'timezone': 'Europe/Moscow',
    }
    if not is_trading_day:
        result['next_open'] = _next_weekday_open(now_utc).astimezone(_MSK).isoformat()
        return result
    result['is_open'] = start_local <= now_msk <= end_local
    if now_msk < start_local:
        result['next_open'] = start_local.astimezone(_MSK).isoformat()
    elif now_msk > end_local:
        result['next_open'] = _next_trading_day_open_after(now_utc + timedelta(seconds=1)).astimezone(_MSK).isoformat()
    else:
        result['next_open'] = _next_trading_day_open_after(end_local.astimezone(timezone.utc)).astimezone(_MSK).isoformat()
    return result

def get_schedule_snapshot(*, session_type: str = 'all', now: datetime | None = None) -> dict[str, Any]:
    now_utc = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    now_msk = now_utc.astimezone(_MSK)
    today_key = now_msk.date().isoformat()
    day = (_CACHE.get('days') or {}).get(today_key)
    source = _CACHE.get('source') or 'static'
    result = {
        'source': source,
        'exchange': _CACHE.get('exchange') or 'MOEX',
        'trading_day': 'unknown',
        'is_trading_day': None,
        'is_open': None,
        'current_session_start': None,
        'current_session_end': None,
        'next_open': None,
        'error': None,
        'warning': _CACHE.get('warning'),
        'fetched_at': _CACHE.get('fetched_at'),
        'timezone': 'Europe/Moscow',
    }
    if not day:
        if source == 'static':
            return _static_schedule_snapshot(session_type=session_type, now_utc=now_utc)
        return _normalize_snapshot_with_static_guard(result, now_utc=now_utc, session_type=session_type)

    result['trading_day'] = today_key
    result['is_trading_day'] = bool(day.get('is_trading_day'))
    if not result['is_trading_day']:
        result['next_open'] = _next_trading_day_open_after(now_utc).astimezone(_MSK).isoformat()
        return result

    start_dt, end_dt = _resolve_bounds(day, session_type)
    if start_dt and end_dt:
        result['current_session_start'] = start_dt.astimezone(_MSK).isoformat()
        result['current_session_end'] = end_dt.astimezone(_MSK).isoformat()
        result['is_open'] = start_dt <= now_utc <= end_dt
        if now_utc < start_dt:
            result['next_open'] = start_dt.astimezone(_MSK).isoformat()
        else:
            future_keys = sorted(k for k in (_CACHE.get('days') or {}).keys() if k > today_key)
            for key in future_keys:
                future_day = (_CACHE.get('days') or {}).get(key)
                if not future_day or not future_day.get('is_trading_day'):
                    continue
                future_start, _ = _resolve_bounds(future_day, session_type)
                if future_start:
                    result['next_open'] = future_start.astimezone(_MSK).isoformat()
                    break
            if not result['next_open']:
                anchor = end_dt if result['is_open'] else now_utc
                result['next_open'] = _next_trading_day_open_after(anchor + timedelta(seconds=1)).astimezone(_MSK).isoformat()
    return _normalize_snapshot_with_static_guard(result, now_utc=now_utc, session_type=session_type)


def get_cached_session_bounds(session_type: str = 'all', now: datetime | None = None) -> tuple[datetime | None, datetime | None, bool | None]:
    snapshot = get_schedule_snapshot(session_type=session_type, now=now)
    if snapshot.get('source') != 'broker' or snapshot.get('is_trading_day') is None:
        return None, None, None
    start = _parse_ts(snapshot.get('current_session_start'))
    end = _parse_ts(snapshot.get('current_session_end'))
    return start, end, snapshot.get('is_open')
