"""
P5-05: VWAP Bounce Strategy.

Logic:
  BUY  — price dipped below VWAP and bounced back above (close > VWAP)
         AND volume confirms (vol_ratio > 1.2)
         AND RSI not overbought (< 70)
  SELL — price spiked above VWAP and rejected back below (close < VWAP)
         AND volume confirms
         AND RSI not oversold (> 30)

SL: 1.5 ATR from entry (beyond the bounce zone)
TP: 2.5 ATR (reward target)
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from apps.worker.decision_engine.indicators import (
    calc_atr, calc_rsi, calc_vwap, calc_volume_ratio,
)
from core.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)


class VWAPBounceStrategy(BaseStrategy):

    @property
    def name(self) -> str:
        return "vwap_bounce"

    @property
    def lookback(self) -> int:
        return 30


    def __init__(self, min_vol_ratio: float = 1.2, rsi_period: int = 14):
        self.min_vol_ratio = min_vol_ratio
        self.rsi_period = rsi_period

    def analyze(self, instrument_id: str, candles: list[dict]) -> Optional[dict]:
        if len(candles) < self.lookback:
            return None

        closes  = [float(c["close"])  for c in candles]
        highs   = [float(c["high"])   for c in candles]
        lows    = [float(c["low"])    for c in candles]
        volumes = [float(c.get("volume", 0)) for c in candles]

        vwap = calc_vwap(highs, lows, closes, volumes)
        if vwap is None:
            return None

        atr = calc_atr(highs, lows, closes, 14)
        if not atr or atr < 1e-9:
            atr = closes[-1] * 0.005

        rsi = calc_rsi(closes, self.rsi_period)
        vol_ratio = calc_volume_ratio(volumes, 20)

        current = closes[-1]
        prev    = closes[-2] if len(closes) >= 2 else current

        # Volume confirmation
        vol_ok = vol_ratio is not None and vol_ratio >= self.min_vol_ratio

        side = None
        entry = current
        sl = tp = 0.0

        # BUY bounce: was below VWAP, now back above + volume + RSI not hot
        if prev < vwap and current > vwap and vol_ok:
            if rsi is None or rsi < 70:
                side = "BUY"
                sl = entry - atr * 1.5
                tp = entry + atr * 2.5

        # SELL rejection: was above VWAP, now back below + volume + RSI not cold
        elif prev > vwap and current < vwap and vol_ok:
            if rsi is None or rsi > 30:
                side = "SELL"
                sl = entry + atr * 1.5
                tp = entry - atr * 2.5

        if not side:
            return None

        sl_dist = abs(entry - sl)
        tp_dist = abs(tp - entry)
        r = round(tp_dist / sl_dist, 2) if sl_dist > 1e-9 else 1.0

        if r < 1.2:
            return None

        logger.debug("VWAPBounce: %s %s entry=%.4f vwap=%.4f vol_ratio=%.2f",
                     instrument_id, side, entry, vwap, vol_ratio or 0)

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
            "reason": f"VWAPBounce: {'price reclaimed VWAP' if side == 'BUY' else 'price rejected from VWAP'}",
            "meta": {
                "strategy": "vwap_bounce_v1",
                "vwap": round(vwap, 4),
                "vol_ratio": round(vol_ratio, 3) if vol_ratio else None,
                "rsi14": round(rsi, 1) if rsi else None,
                "atr": round(atr, 4),
            },
        }
