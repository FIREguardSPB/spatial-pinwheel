"""
P5-05: StrategySelector — instantiates the active strategy from Settings.strategy_name.

Usage in Worker:
    selector = StrategySelector()
    strategy = selector.get(settings.strategy_name)
    signal   = strategy.analyze(ticker, candles)
"""
from __future__ import annotations

import logging

from core.strategy.base import BaseStrategy
from core.strategy.breakout import BreakoutStrategy
from core.strategy.mean_reversion import MeanReversionStrategy
from core.strategy.vwap_bounce import VWAPBounceStrategy

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type[BaseStrategy]] = {
    "breakout":       BreakoutStrategy,
    "mean_reversion": MeanReversionStrategy,
    "vwap_bounce":    VWAPBounceStrategy,
}


class StrategySelector:
    """
    Returns the appropriate strategy instance by name.
    Caches instances so the same object is reused between calls.
    """

    def __init__(self):
        self._cache: dict[str, BaseStrategy] = {}

    def get(self, name: str | None) -> BaseStrategy:
        """
        Return the strategy for the given name.
        Falls back to BreakoutStrategy if name is unknown.
        """
        key = (name or "breakout").lower().strip()

        if key not in self._cache:
            cls = _REGISTRY.get(key)
            if cls is None:
                logger.warning("Unknown strategy '%s' — falling back to 'breakout'", key)
                cls = BreakoutStrategy
                key = "breakout"
            self._cache[key] = cls()
            logger.info("Strategy activated: %s (%s)", key, cls.__name__)

        return self._cache[key]

    @staticmethod
    def available() -> list[str]:
        """List of all registered strategy names."""
        return list(_REGISTRY.keys())
