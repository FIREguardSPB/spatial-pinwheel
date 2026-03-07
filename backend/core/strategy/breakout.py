from core.strategy.base import BaseStrategy
"""
P2-03: Breakout Strategy — добавлен SELL (Short) сигнал + реальный расчёт R/R.

BUY  — пробой вверх: close > max(high[-lookback:-1])
SELL — пробой вниз:  close < min(low[-lookback:-1])

SL/TP рассчитываются через ATR(14) для более точного риска.
R считается как (tp - entry) / (entry - sl) для BUY.
"""
import uuid
import time
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def _calc_atr(candles: list, period: int = 14) -> float:
    """Простой ATR без библиотек."""
    if len(candles) < period + 1:
        # Fallback: среднее (high - low) за доступные свечи
        ranges = [float(c["high"]) - float(c["low"]) for c in candles]
        return sum(ranges) / len(ranges) if ranges else 0.0

    true_ranges = []
    for i in range(1, len(candles)):
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        prev_close = float(candles[i - 1]["close"])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    # Простое среднее последних period значений (SMA-ATR)
    return sum(true_ranges[-period:]) / period


class BreakoutStrategy(BaseStrategy):

    def __init__(self, lookback: int = 20):
        self._lookback = lookback

    @property
    def name(self) -> str:
        return "breakout"

    @property
    def lookback(self) -> int:
        return self._lookback

    def analyze(self, instrument_id: str, candles: List[dict]) -> Optional[dict]:
        """
        Анализирует историю свечей.
        Возвращает dict сигнала или None.
        """
        if len(candles) < self._lookback:
            return None

        window = candles[-self._lookback:]
        # Предыдущие N-1 свечей (без текущей)
        prev = window[:-1]
        current = window[-1]

        range_high = max(float(c["high"]) for c in prev)
        range_low  = min(float(c["low"])  for c in prev)
        current_close = float(current["close"])

        # ATR для расчёта SL/TP
        atr = _calc_atr(candles[-20:], period=min(14, len(candles) - 1))
        if atr < 1e-9:
            atr = current_close * 0.005  # fallback 0.5%

        signal_side = None
        entry = current_close
        sl = 0.0
        tp = 0.0

        # ── BUY: пробой вверх ─────────────────────────────────────────────────
        if current_close > range_high:
            signal_side = "BUY"
            sl = current_close - atr * 2.0   # SL = 2×ATR ниже входа
            tp = current_close + atr * 3.0   # TP = 3×ATR выше входа (R/R = 1.5)

        # ── SELL: пробой вниз (P2-03 новая логика) ────────────────────────────
        elif current_close < range_low:
            signal_side = "SELL"
            sl = current_close + atr * 2.0   # SL = 2×ATR выше входа
            tp = current_close - atr * 3.0   # TP = 3×ATR ниже входа (R/R = 1.5)

        if not signal_side:
            return None

        # ── P2-03: реальный расчёт R ──────────────────────────────────────────
        sl_distance = abs(entry - sl)
        tp_distance = abs(tp - entry)
        r = round(tp_distance / sl_distance, 2) if sl_distance > 1e-9 else 1.5

        logger.debug(
            "BreakoutStrategy: %s %s entry=%.4f sl=%.4f tp=%.4f atr=%.4f R=%.2f",
            instrument_id, signal_side, entry, sl, tp, atr, r,
        )

        return {
            "id": f"sig_{uuid.uuid4().hex[:12]}",
            "instrument_id": instrument_id,
            "ts": int(time.time() * 1000),
            "side": signal_side,
            "entry": round(entry, 4),
            "sl": round(sl, 4),
            "tp": round(tp, 4),
            "size": 10.0,  # placeholder — будет пересчитан через RiskManager.calculate_position_size в P2-04
            "r": r,
            "status": "pending_review",
            "reason": f"Breakout {'above' if signal_side == 'BUY' else 'below'} {self._lookback}-bar range",
            "meta": {
                "strategy": "breakout_v2",
                "atr": round(atr, 4),
                "range_high": round(range_high, 4),
                "range_low": round(range_low, 4),
            },
        }
