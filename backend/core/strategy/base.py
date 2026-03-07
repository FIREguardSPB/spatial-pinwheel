"""
P5-05: Abstract base class for all trading strategies.
All strategies implement analyze(instrument_id, candles) → dict | None.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional


class BaseStrategy(ABC):
    """Common interface for all trading strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name."""
        ...

    @property
    @abstractmethod
    def lookback(self) -> int:
        """Minimum number of candles required."""
        ...

    @abstractmethod
    def analyze(self, instrument_id: str, candles: list[dict]) -> Optional[dict]:
        """
        Analyze candle history and return a signal dict or None.

        Signal dict keys: id, instrument_id, ts, side, entry, sl, tp, size, r,
                          status, reason, meta
        """
        ...
