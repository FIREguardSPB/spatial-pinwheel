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


def _as_epoch_ms(value: Any) -> int:
    ts = int(value or 0)
    if ts <= 0:
        return 0
    # Worker aggregator stores candle times in epoch seconds, while DB/API paths
    # often use epoch milliseconds. Normalize both into milliseconds.
    if ts < 10_000_000_000:
        return ts * 1000
    return ts


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


def build_higher_tf_continuation_thesis(candles: list[dict[str, Any]], *, timeframe: str) -> dict[str, Any] | None:
    tf = normalize_timeframe(timeframe, '15m')
    if tf not in {'5m', '15m', '30m', '1h'}:
        return None
    if len(candles) < 20:
        return None

    closes = [float(c.get('close') or 0.0) for c in candles[-20:]]
    highs = [float(c.get('high') or c.get('close') or 0.0) for c in candles[-20:]]
    lows = [float(c.get('low') or c.get('close') or 0.0) for c in candles[-20:]]
    if min(closes) <= 0:
        return None

    start_close = closes[0]
    end_close = closes[-1]
    trend_up = end_close > start_close * 1.01
    trend_down = end_close < start_close * 0.99
    if not trend_up and not trend_down:
        return None

    prev_high = max(highs[:-1])
    prev_low = min(lows[:-1])
    last_close = closes[-1]
    last_high = highs[-1]
    last_low = lows[-1]
    recent_closes = closes[-5:]
    recent_highs = highs[-5:]
    recent_lows = lows[-5:]
    avg_range = sum((h - l) for h, l in zip(highs, lows)) / max(1, len(highs))
    near_buffer = max(avg_range * 0.35, last_close * 0.0015)
    pullback_window = max(4, len(closes) // 4)

    def _payload(side: str, structure: str) -> dict[str, Any]:
        return {
            'side': side,
            'thesis_timeframe': tf,
            'thesis_type': 'continuation',
            'structure': structure,
        }

    if trend_up and last_close >= prev_high - near_buffer and last_high >= prev_high:
        return _payload('BUY', 'near_high_break_continuation')
    if trend_down and last_close <= prev_low + near_buffer and last_low <= prev_low:
        return _payload('SELL', 'near_low_break_continuation')

    fast_trend_up = recent_closes[-1] > recent_closes[0] * 1.003
    fast_trend_down = recent_closes[-1] < recent_closes[0] * 0.997
    recent_pullback_low = min(lows[-pullback_window:])
    recent_pullback_high = max(highs[-pullback_window:])
    higher_low_preserved = recent_pullback_low >= (start_close + (end_close - start_close) * 0.58)
    lower_high_preserved = recent_pullback_high <= (start_close + (end_close - start_close) * 0.42)
    reclaimed_recent_high = last_close >= max(recent_highs[:-1]) - near_buffer * 0.8
    reclaimed_recent_low = last_close <= min(recent_lows[:-1]) + near_buffer * 0.8

    if trend_up and last_close >= prev_high - near_buffer * 1.8 and fast_trend_up:
        return _payload('BUY', 'trend_continuation')
    if trend_down and last_close <= prev_low + near_buffer * 1.8 and fast_trend_down:
        return _payload('SELL', 'trend_continuation')

    if trend_up and higher_low_preserved and recent_closes[-1] > recent_closes[-2] > recent_closes[-3] and reclaimed_recent_high:
        return _payload('BUY', 'pullback_hold_continuation')
    if trend_down and lower_high_preserved and recent_closes[-1] < recent_closes[-2] < recent_closes[-3] and reclaimed_recent_low:
        return _payload('SELL', 'pullback_hold_continuation')

    recent_sweep_low = min(recent_lows)
    recent_sweep_high = max(recent_highs)

    if trend_down and recent_sweep_low <= prev_low + near_buffer and last_close >= min(recent_closes[:-1]) + avg_range * 1.4 and last_close >= recent_closes[-2] + avg_range * 0.5:
        return _payload('BUY', 'failed_breakdown_reclaim')
    if trend_up and recent_sweep_high >= prev_high - near_buffer and last_close <= max(recent_closes[:-1]) - avg_range * 1.4 and last_close <= recent_closes[-2] - avg_range * 0.5:
        return _payload('SELL', 'failed_breakout_reclaim')
    return None


def select_timeframe_stack_for_regime(regime_input: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(regime_input or {})
    trend_strength = max(0.0, min(1.0, float(payload.get('trend_strength') or 0.0)))
    noise_ratio = max(0.0, min(1.0, float(payload.get('noise_ratio') or 0.0)))
    event_pressure = max(0.0, min(1.0, float(payload.get('event_pressure') or 0.0)))
    instrument_class = str(payload.get('instrument_class') or 'equity')

    profile = 'balanced'
    context_tf = '15m'
    thesis_tfs = ['5m', '15m']
    execution_tf = '1m'
    allows_1m_thesis_exception = False

    if trend_strength >= 0.7 and noise_ratio <= 0.3:
        profile = 'trend_continuation'
        context_tf = '30m'
        thesis_tfs = ['15m', '5m']
    elif event_pressure >= 0.85 and noise_ratio >= 0.75:
        profile = 'event_burst'
        context_tf = '15m'
        thesis_tfs = ['5m', '3m', '1m']
        execution_tf = '1m'
        allows_1m_thesis_exception = instrument_class in {'futures', 'crypto', 'fx', 'index'}
        if not allows_1m_thesis_exception:
            thesis_tfs = ['5m', '3m']

    thesis_tfs = [normalize_timeframe(tf, '5m') for tf in thesis_tfs]
    deduped: list[str] = []
    for tf in thesis_tfs:
        if tf not in deduped:
            deduped.append(tf)

    return {
        'market_regime_profile': profile,
        'context_timeframe': context_tf,
        'thesis_timeframes': deduped,
        'execution_timeframe': execution_tf,
        'allows_1m_thesis_exception': allows_1m_thesis_exception,
    }


def _infer_source_step_ms(candles: list[dict[str, Any]]) -> int:
    timestamps = sorted({_as_epoch_ms(item.get('time')) for item in candles if _as_epoch_ms(item.get('time')) > 0})
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
        ts = _as_epoch_ms(candle.get('time'))
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
