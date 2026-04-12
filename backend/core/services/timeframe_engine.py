from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

_TIMEFRAME_MS: dict[str, int] = {
    '1m': 60_000,
    '3m': 180_000,
    '5m': 300_000,
    '15m': 900_000,
    '30m': 1_800_000,
    '1h': 3_600_000,
    '4h': 14_400_000,
    '1d': 86_400_000,
}
_MSK = ZoneInfo('Europe/Moscow')


def normalize_timeframe(value: str | None, default: str = '1m') -> str:
    raw = str(value or default).strip().lower()
    return raw if raw in _TIMEFRAME_MS else default


def timeframe_ms(value: str | None, default: str = '1m') -> int:
    return _TIMEFRAME_MS[normalize_timeframe(value, default)]


def timeframe_rank(value: str | None) -> int:
    tf = normalize_timeframe(value)
    ordered = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d']
    try:
        return ordered.index(tf)
    except ValueError:
        return 0


def max_timeframe(a: str | None, b: str | None) -> str:
    return normalize_timeframe(a if timeframe_rank(a) >= timeframe_rank(b) else b)


def next_higher_timeframe(value: str | None) -> str:
    ordered = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d']
    tf = normalize_timeframe(value)
    idx = ordered.index(tf)
    return ordered[min(idx + 1, len(ordered) - 1)]


def _infer_source_step_ms(candles: list[dict[str, Any]]) -> int:
    timestamps = sorted({int(item.get('time') or 0) for item in candles if int(item.get('time') or 0) > 0})
    if len(timestamps) < 2:
        return _TIMEFRAME_MS['1m']
    deltas = [cur - prev for prev, cur in zip(timestamps[:-1], timestamps[1:]) if cur - prev > 0]
    if not deltas:
        return _TIMEFRAME_MS['1m']
    try:
        step = int(median(deltas))
    except Exception:
        step = min(deltas)
    return max(_TIMEFRAME_MS['1m'], step)


def _local_trading_day(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=_MSK).strftime('%Y-%m-%d')


def _default_anchor_ms(ts_ms: int, tf: str) -> int:
    local_dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=_MSK)
    session_start = datetime(local_dt.year, local_dt.month, local_dt.day, 6, 50, tzinfo=_MSK)
    if tf == '1d':
        day_start = datetime(local_dt.year, local_dt.month, local_dt.day, 0, 0, tzinfo=_MSK)
        return int(day_start.timestamp() * 1000)
    return int(session_start.timestamp() * 1000)


def _bucket_start(ts_ms: int, *, step_ms: int, anchor_ms: int) -> int:
    return anchor_ms + ((ts_ms - anchor_ms) // step_ms) * step_ms


def resample_candles(
    candles: list[dict[str, Any]],
    timeframe: str,
    *,
    drop_last_incomplete: bool = True,
    anchor_mode: str = 'session',
) -> list[dict[str, Any]]:
    tf = normalize_timeframe(timeframe)
    if tf == '1m':
        return list(candles)
    ordered = sorted(candles, key=lambda item: int(item.get('time') or 0))
    if not ordered:
        return []

    step_ms = timeframe_ms(tf)
    source_step_ms = _infer_source_step_ms(ordered)
    buckets: dict[tuple[str, int], dict[str, Any]] = {}
    day_anchors: dict[str, int] = {}

    for candle in ordered:
        ts = int(candle.get('time') or 0)
        if ts <= 0:
            continue
        day_key = _local_trading_day(ts)
        if anchor_mode == 'epoch':
            anchor_ms = 0
        else:
            anchor_ms = day_anchors.setdefault(day_key, _default_anchor_ms(ts, tf))
        bucket_ts = _bucket_start(ts, step_ms=step_ms, anchor_ms=anchor_ms)
        bucket_key = (day_key, bucket_ts)
        current = buckets.get(bucket_key)
        o = float(candle.get('open') or candle.get('close') or 0.0)
        h = float(candle.get('high') or candle.get('close') or 0.0)
        l = float(candle.get('low') or candle.get('close') or 0.0)
        c = float(candle.get('close') or 0.0)
        v = int(candle.get('volume') or 0)
        if current is None:
            buckets[bucket_key] = {
                'time': bucket_ts,
                'open': o,
                'high': h,
                'low': l,
                'close': c,
                'volume': v,
                '_last_input_ts': ts,
            }
        else:
            current['high'] = max(float(current['high']), h)
            current['low'] = min(float(current['low']), l)
            current['close'] = c
            current['volume'] = int(current.get('volume') or 0) + v
            current['_last_input_ts'] = ts

    result: list[dict[str, Any]] = []
    for _, bucket in sorted(buckets.items(), key=lambda item: item[1]['time']):
        bucket_start = int(bucket['time'])
        is_complete = True
        if drop_last_incomplete:
            expected_last_input = bucket_start + step_ms - source_step_ms
            is_complete = int(bucket.get('_last_input_ts') or 0) >= expected_last_input
        if is_complete:
            cleaned = dict(bucket)
            cleaned.pop('_last_input_ts', None)
            result.append(cleaned)
    return result


def detect_trend(candles: list[dict[str, Any]]) -> tuple[str, float | None]:
    closes = [float(c.get('close') or 0.0) for c in candles if c.get('close') is not None]
    if len(closes) < 10:
        return 'flat', None
    short_n = min(10, len(closes))
    long_n = min(30, len(closes))
    ema_short = sum(closes[-short_n:]) / short_n
    ema_long_now = sum(closes[-long_n:]) / long_n
    prev_slice = closes[:-1]
    if len(prev_slice) >= long_n:
        ema_long_prev = sum(prev_slice[-long_n:]) / long_n
    else:
        ema_long_prev = ema_long_now
    slope = ema_long_now - ema_long_prev
    tol = max(abs(ema_long_now) * 0.0005, 1e-9)
    if ema_short > ema_long_now + tol and slope >= -tol:
        return 'up', slope
    if ema_short < ema_long_now - tol and slope <= tol:
        return 'down', slope
    return 'flat', slope


def align_signal_to_execution(signal: dict[str, Any], execution_price: float) -> dict[str, Any]:
    side = str(signal.get('side') or '')
    entry = float(signal.get('entry') or 0.0)
    sl = float(signal.get('sl') or 0.0)
    tp = float(signal.get('tp') or 0.0)
    if execution_price <= 0 or entry <= 0 or sl <= 0 or tp <= 0 or side not in {'BUY', 'SELL'}:
        return signal
    stop_abs = abs(entry - sl)
    target_abs = abs(tp - entry)
    if side == 'BUY':
        signal['entry'] = round(float(execution_price), 6)
        signal['sl'] = round(float(execution_price - stop_abs), 6)
        signal['tp'] = round(float(execution_price + target_abs), 6)
    else:
        signal['entry'] = round(float(execution_price), 6)
        signal['sl'] = round(float(execution_price + stop_abs), 6)
        signal['tp'] = round(float(execution_price - target_abs), 6)
    signal['r'] = round(float(target_abs / stop_abs), 4) if stop_abs > 1e-9 else float(signal.get('r') or 0.0)
    return signal
