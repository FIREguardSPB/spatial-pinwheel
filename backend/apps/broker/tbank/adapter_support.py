from __future__ import annotations

from datetime import datetime
from typing import Any


def normalize_instrument_id(instrument_id: str) -> str:
    raw = (instrument_id or '').strip()
    if not raw:
        return raw
    if ':' in raw:
        left, right = raw.split(':', 1)
        return f"{left.upper()}:{right.upper()}"
    if len(raw) == 36 and '-' in raw:
        return raw
    if '_' in raw:
        return raw.upper()
    return f"TQBR:{raw.upper()}"


def interval_to_rest(interval_str: str) -> str:
    return {
        '1m': 'CANDLE_INTERVAL_1_MIN',
        '5m': 'CANDLE_INTERVAL_5_MIN',
        '15m': 'CANDLE_INTERVAL_15_MIN',
        '1h': 'CANDLE_INTERVAL_HOUR',
        '4h': 'CANDLE_INTERVAL_4_HOUR',
        '1d': 'CANDLE_INTERVAL_DAY',
    }.get(interval_str, 'CANDLE_INTERVAL_1_MIN')


def parse_api_timestamp(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return 0
    try:
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        return int(datetime.fromisoformat(text).timestamp())
    except Exception:
        return 0
