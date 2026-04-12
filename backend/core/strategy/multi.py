"""
Base multi-strategy orchestration for Phase 1.

Supports running several strategies in parallel on the same candle history and
selecting the strongest candidate with deterministic conflict resolution.

The current implementation intentionally keeps equal/static weights and a very
simple conflict manager so it can be introduced without breaking the existing
single-strategy pipeline.
"""
from __future__ import annotations

import logging
from copy import deepcopy
from typing import Iterable, Optional

from core.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)


_DEFAULT_WEIGHTS: dict[str, float] = {
    "breakout": 1.00,
    "mean_reversion": 0.97,
    "vwap_bounce": 0.95,
}


class CompositeStrategy(BaseStrategy):
    """Run multiple strategies and return the strongest candidate."""

    def __init__(self, strategies: Iterable[BaseStrategy], weights: Optional[dict[str, float]] = None):
        self._strategies = list(strategies)
        if not self._strategies:
            raise ValueError("CompositeStrategy requires at least one strategy")
        self._weights = {**_DEFAULT_WEIGHTS, **(weights or {})}

    @property
    def name(self) -> str:
        return ",".join(strategy.name for strategy in self._strategies)

    @property
    def lookback(self) -> int:
        return max(strategy.lookback for strategy in self._strategies)

    @property
    def strategies(self) -> list[BaseStrategy]:
        return list(self._strategies)

    def analyze(self, instrument_id: str, candles: list[dict]) -> Optional[dict]:
        candidates: list[dict] = []
        for strategy in self._strategies:
            try:
                signal = strategy.analyze(instrument_id, candles)
            except Exception:
                logger.exception("Strategy %s crashed for %s", strategy.name, instrument_id)
                continue
            if not signal:
                continue
            candidate = deepcopy(signal)
            meta = dict(candidate.get("meta") or {})
            strategy_name = strategy.name
            rr_value = float(candidate.get("r") or 0.0)
            weight = float(self._weights.get(strategy_name, 1.0))
            weighted_score = round(rr_value * weight, 4)
            meta.update({
                "strategy_name": strategy_name,
                "strategy_weight": weight,
                "strategy_weighted_score": weighted_score,
            })
            candidate["meta"] = meta
            candidates.append(candidate)

        if not candidates:
            return None

        # Conflict manager (Phase 1): pick the strongest weighted candidate.
        # Ties: prefer higher raw R, then keep deterministic alphabetical order.
        ranked = sorted(
            candidates,
            key=lambda item: (
                float(item.get("meta", {}).get("strategy_weighted_score", 0.0)),
                float(item.get("r") or 0.0),
                item.get("meta", {}).get("strategy_name", ""),
            ),
            reverse=True,
        )
        selected = ranked[0]
        selected_meta = dict(selected.get("meta") or {})
        selected_meta["multi_strategy"] = {
            "mode": "parallel_best_candidate",
            "candidate_count": len(ranked),
            "selected_strategy": selected_meta.get("strategy_name"),
            "candidates": [
                {
                    "strategy": item.get("meta", {}).get("strategy_name"),
                    "side": item.get("side"),
                    "r": float(item.get("r") or 0.0),
                    "weight": float(item.get("meta", {}).get("strategy_weight", 1.0)),
                    "weighted_score": float(item.get("meta", {}).get("strategy_weighted_score", 0.0)),
                }
                for item in ranked
            ],
        }
        selected["meta"] = selected_meta
        selected["reason"] = (
            f"MultiStrategy selected {selected_meta.get('strategy_name')} "
            f"from {len(ranked)} candidate(s): {selected.get('reason', '')}"
        ).strip()
        logger.info(
            "MultiStrategy selected %s for %s (candidates=%s)",
            selected_meta.get("strategy_name"),
            instrument_id,
            ", ".join(
                f"{item.get('meta', {}).get('strategy_name')}:{item.get('side')}@{float(item.get('meta', {}).get('strategy_weighted_score', 0.0)):.2f}"
                for item in ranked
            ),
        )
        return selected
