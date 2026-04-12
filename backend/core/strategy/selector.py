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
from core.strategy.multi import CompositeStrategy
from core.strategy.vwap_bounce import VWAPBounceStrategy

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type[BaseStrategy]] = {
    "breakout":       BreakoutStrategy,
    "mean_reversion": MeanReversionStrategy,
    "vwap_bounce":    VWAPBounceStrategy,
}


def _parse_strategy_names(name: str | None) -> list[str]:
    raw = (name or "breakout").replace(";", ",")
    parts = [part.strip().lower() for part in raw.split(",") if part.strip()]
    seen: list[str] = []
    for part in parts or ["breakout"]:
        if part not in seen:
            seen.append(part)
    return seen


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
        Supports comma-separated multi-strategy configuration.
        """
        names = _parse_strategy_names(name)
        if len(names) > 1:
            return self.get_composite(names)

        key = names[0]
        if key not in self._cache:
            cls = _REGISTRY.get(key)
            if cls is None:
                logger.warning("Unknown strategy '%s' — falling back to 'breakout'", key)
                cls = BreakoutStrategy
                key = "breakout"
            self._cache[key] = cls()
            logger.info("Strategy activated: %s (%s)", key, cls.__name__)

        return self._cache[key]

    def get_many(self, names: list[str] | str | None) -> list[BaseStrategy]:
        parsed = names if isinstance(names, list) else _parse_strategy_names(names)
        return [self.get(name) for name in parsed]

    def get_composite(self, names: list[str] | str | None) -> CompositeStrategy:
        parsed = names if isinstance(names, list) else _parse_strategy_names(names)
        cache_key = "multi:" + ",".join(parsed)
        cached = self._cache.get(cache_key)
        if cached and isinstance(cached, CompositeStrategy):
            return cached

        strategies: list[BaseStrategy] = []
        for item in parsed:
            strategy = self.get(item)
            if isinstance(strategy, CompositeStrategy):
                strategies.extend(strategy.strategies)
            else:
                strategies.append(strategy)
        composite = CompositeStrategy(strategies)
        self._cache[cache_key] = composite
        logger.info("Strategy activated: %s (CompositeStrategy)", cache_key)
        return composite

    @staticmethod
    def available() -> list[str]:
        """List of all registered strategy names."""
        return list(_REGISTRY.keys())

    @staticmethod
    def parse_names(name: str | None) -> list[str]:
        return _parse_strategy_names(name)
