"""
P5-05: Mean Reversion Strategy — Bollinger Bands bounce.

Logic:
  BUY  — close < lower band (oversold) AND stochastic K < 30 (confirmation)
  SELL — close > upper band (overbought) AND stochastic K > 70

SL/TP:
  BUY:  SL = lower - 0.5 ATR, TP = middle band (mean reversion target)
  SELL: SL = upper + 0.5 ATR, TP = middle band

Works best in ranging markets — good complement to Breakout.
"""
from __future__ import annotations

import time
import uuid
import logging
from typing import Optional

from core.strategy.base import BaseStrategy
from apps.worker.decision_engine.indicators import (
    calc_bollinger, calc_stochastic, calc_atr,
)

logger = logging.getLogger(__name__)


class MeanReversionStrategy(BaseStrategy):

    @property
    def name(self) -> str:
        return "mean_reversion"

    @property
    def lookback(self) -> int:
        return 25


    def __init__(self, bb_period: int = 20, bb_std: float = 2.0,
                 stoch_k: int = 14, stoch_d: int = 3):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.stoch_k = stoch_k
        self.stoch_d = stoch_d

    def analyze(self, instrument_id: str, candles: list[dict]) -> Optional[dict]:
        if len(candles) < self.lookback:
            return None

        closes = [float(c["close"]) for c in candles]
        highs  = [float(c["high"])  for c in candles]
        lows   = [float(c["low"])   for c in candles]

        bb = calc_bollinger(closes, self.bb_period, self.bb_std)
        if not bb:
            return None
        upper, middle, lower = bb

        stoch = calc_stochastic(highs, lows, closes, self.stoch_k, self.stoch_d)
        atr = calc_atr(highs, lows, closes, 14)
        if atr is None or atr < 1e-9:
            atr = closes[-1] * 0.005

        current = closes[-1]
        side = None
        entry = current

        # BUY: price below lower band + stochastic oversold
        if current < lower:
            if stoch is None or stoch[0] < 35:  # K < 35 = oversold confirmation
                side = "BUY"
                sl = entry - atr * 1.5    # below current entry price
                tp = middle               # target = mean

        # SELL: price above upper band + stochastic overbought
        elif current > upper:
            if stoch is None or stoch[0] > 65:  # K > 65 = overbought confirmation
                side = "SELL"
                sl = entry + atr * 1.5    # above current entry price
                tp = middle

        if not side:
            return None

        sl_dist = abs(entry - sl)
        tp_dist = abs(tp - entry)
        r = round(tp_dist / sl_dist, 2) if sl_dist > 1e-9 else 1.0

        if r < 1.0:  # Skip if R/R < 1
            return None

        logger.debug("MeanReversion: %s %s entry=%.4f bb=[%.4f,%.4f,%.4f]",
                     instrument_id, side, entry, upper, middle, lower)

        return {
            "id": f"sig_{uuid.uuid4().hex[:12]}",
            "instrument_id": instrument_id,
            "ts": int(time.time() * 1000),
            "side": side,
            "entry": round(entry, 4),
            "sl": round(sl, 4),
            "tp": round(tp, 4),
            "size": 10.0,
            "r": r,
            "status": "pending_review",
            "reason": f"MeanReversion: {'below lower BB' if side == 'BUY' else 'above upper BB'}",
            "meta": {
                "strategy": "mean_reversion_v1",
                "bb_upper": round(upper, 4),
                "bb_middle": round(middle, 4),
                "bb_lower": round(lower, 4),
                "stoch_k": stoch[0] if stoch else None,
                "atr": round(atr, 4),
            },
        }
