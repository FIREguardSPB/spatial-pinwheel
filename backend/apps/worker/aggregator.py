"""
P3-03: CandleAggregator — агрегация тиков в OHLCV свечи.

Отвечает только за:
  - Определение начала нового бара
  - Обновление текущей свечи
  - Финализацию (закрытие) предыдущей и добавление в историю
"""
from collections import deque
from decimal import Decimal
from typing import NamedTuple

from core.utils.time import ensure_sec


class Candle(NamedTuple):
    instrument_id: str
    time: int          # Unix seconds (frame start)
    open: float
    high: float
    low: float
    close: float
    volume: int
    is_complete: bool


class CandleAggregator:
    """
    Aggregates raw tick stream into OHLCV candles of a fixed timeframe.

    Args:
        frame_sec: Candle duration in seconds (60 = 1m, 300 = 5m, etc.)
        history_size: Max completed candles to keep per instrument.
    """

    def __init__(self, frame_sec: int = 60, history_size: int = 200):
        self.frame_sec = frame_sec
        self.history_size = history_size
        self._current: dict[str, dict] = {}          # live partial candle per ticker
        self._history: dict[str, deque] = {}         # completed candles per ticker

    def on_tick(self, tick: dict) -> tuple[Candle, bool]:
        """
        Process a single tick.

        Returns:
            (current_candle, bar_closed)
            bar_closed=True means a new bar just started and the previous was finalized.
        """
        ticker = tick["instrument_id"]
        tick_ts = ensure_sec(tick["time"])
        frame_start = (tick_ts // self.frame_sec) * self.frame_sec

        if ticker not in self._history:
            self._history[ticker] = deque(maxlen=self.history_size)

        candle = self._current.get(ticker)
        bar_closed = False

        if not candle or candle["time"] != frame_start:
            # New bar — finalize previous
            if candle:
                self._history[ticker].append(self._to_dict(candle))
                bar_closed = True

            candle = {
                "instrument_id": ticker,
                "time": frame_start,
                "open": float(tick["open"]),
                "high": float(tick["high"]),
                "low": float(tick["low"]),
                "close": float(tick["close"]),
                "volume": int(tick["volume"]),
            }
        else:
            candle["high"] = max(candle["high"], float(tick["high"]))
            candle["low"] = min(candle["low"], float(tick["low"]))
            candle["close"] = float(tick["close"])
            candle["volume"] += int(tick["volume"])

        self._current[ticker] = candle
        return (
            Candle(
                instrument_id=ticker,
                time=candle["time"],
                open=candle["open"],
                high=candle["high"],
                low=candle["low"],
                close=candle["close"],
                volume=candle["volume"],
                is_complete=False,
            ),
            bar_closed,
        )

    def get_history(self, ticker: str) -> list[dict]:
        """Return completed candles + current partial candle as list of dicts."""
        completed = list(self._history.get(ticker, []))
        current = self._current.get(ticker)
        if current:
            completed.append(self._to_dict(current))
        return completed

    def history_len(self, ticker: str) -> int:
        return len(self._history.get(ticker, []))

    def current_price(self, ticker: str) -> float | None:
        c = self._current.get(ticker)
        return c["close"] if c else None

    @staticmethod
    def _to_dict(candle: dict) -> dict:
        return {k: v for k, v in candle.items() if k != "instrument_id"}
