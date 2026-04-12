from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import unittest

from core.strategy.base import BaseStrategy
from core.strategy.multi import CompositeStrategy
from core.strategy.selector import StrategySelector


class _DummyStrategy(BaseStrategy):
    def __init__(self, name: str, signal: dict | None, lookback: int = 10):
        self._name = name
        self._signal = signal
        self._lookback = lookback

    @property
    def name(self) -> str:
        return self._name

    @property
    def lookback(self) -> int:
        return self._lookback

    def analyze(self, instrument_id: str, candles: list[dict]):
        if not self._signal:
            return None
        payload = dict(self._signal)
        payload.setdefault("instrument_id", instrument_id)
        payload.setdefault("side", "BUY")
        payload.setdefault("entry", 100.0)
        payload.setdefault("sl", 99.0)
        payload.setdefault("tp", 102.0)
        payload.setdefault("r", 1.0)
        payload.setdefault("meta", {})
        return payload


class CompositeStrategyTests(unittest.TestCase):
    def test_selects_highest_weighted_candidate(self):
        breakout = _DummyStrategy("breakout", {"r": 1.4, "meta": {"strategy": "breakout_v2"}})
        mean_rev = _DummyStrategy("mean_reversion", {"r": 1.9, "meta": {"strategy": "mean_reversion_v1"}})
        composite = CompositeStrategy([breakout, mean_rev], weights={"breakout": 1.0, "mean_reversion": 0.9})

        result = composite.analyze("TQBR:SBER", [{"close": 1}] * composite.lookback)

        self.assertIsNotNone(result)
        self.assertEqual(result["meta"]["strategy_name"], "mean_reversion")
        self.assertEqual(result["meta"]["multi_strategy"]["candidate_count"], 2)
        self.assertIn("selected_strategy", result["meta"]["multi_strategy"])

    def test_returns_none_when_no_strategy_fires(self):
        composite = CompositeStrategy([
            _DummyStrategy("breakout", None),
            _DummyStrategy("mean_reversion", None),
        ])
        self.assertIsNone(composite.analyze("TQBR:SBER", [{"close": 1}] * composite.lookback))


class StrategySelectorPhase1Tests(unittest.TestCase):
    def setUp(self):
        self.selector = StrategySelector()

    def test_parse_names_deduplicates_and_normalizes(self):
        self.assertEqual(
            self.selector.parse_names(" breakout,mean_reversion, breakout ; vwap_bounce "),
            ["breakout", "mean_reversion", "vwap_bounce"],
        )

    def test_get_returns_composite_for_multiple_names(self):
        strategy = self.selector.get("breakout,mean_reversion")
        self.assertIsInstance(strategy, CompositeStrategy)
        self.assertEqual({item.name for item in strategy.strategies}, {"breakout", "mean_reversion"})


if __name__ == "__main__":
    unittest.main()
