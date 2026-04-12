from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TimeStopPrediction:
    hold_bars: int
    confidence: float = 0.0
    reason: str = "compatibility_stub"


class TimeStopPredictor:
    """Backward-compatible stub.

    The real adaptive exit logic now lives in core.services.adaptive_exit.
    This module exists so older imports do not crash the worker.
    """

    def predict(self, *args: Any, base_hold_bars: int | None = None, **kwargs: Any) -> TimeStopPrediction:
        hold = int(base_hold_bars or kwargs.get('hold_bars') or 12)
        return TimeStopPrediction(hold_bars=max(1, hold), confidence=0.0)


_DEFAULT = TimeStopPredictor()


def get_time_stop_predictor(*args: Any, **kwargs: Any) -> TimeStopPredictor:
    return _DEFAULT
