from typing import List, Optional
import uuid
import time

class BreakoutStrategy:
    def __init__(self, lookback: int = 20):
        self.lookback = lookback

    def analyze(self, instrument_id: str, candles: List[dict]) -> Optional[dict]:
        """
        Analyzes candles (list of dicts or objects with close, high, low).
        Returns dict matching Signal schema or None.
        """
        if len(candles) < self.lookback:
            return None

        # Take last N candles excluding the current forming one usually? 
        # Or including? Let's assume candles[-1] is CLOSED candle passed by generator.
        window = candles[-self.lookback:]
        
        highs = [c['high'] for c in window]
        lows = [c['low'] for c in window]
        current_close = window[-1]['close']
        
        range_high = max(highs[:-1]) # Max of previous N-1
        range_low = min(lows[:-1])
        
        # Simple Breakout Logic
        signal_side = None
        entry = current_close
        sl = 0.0
        tp = 0.0
        
        # ATR-like volatility (approx range of last candle)
        volatility = window[-1]['high'] - window[-1]['low']
        if volatility == 0: volatility = current_close * 0.001

        if current_close > range_high:
            signal_side = "BUY"
            sl = current_close - (volatility * 2.0)
            tp = current_close + (volatility * 3.0) # 1.5R
        elif current_close < range_low:
            # Short logic (optional if we only want Longs for MVP simple stock bot?)
            # TQBR usually allows shorts but requires margin. Let's support BUY only for safety? 
            # Or support both. Let's do BUY only for spec simplicity unless specified.
            # Spec example shows "BUY". "Breakout above range".
            pass

        if signal_side:
            # Generate ID
            sig_id = f"sig_{uuid.uuid4().hex[:12]}"
            return {
                "id": sig_id,
                "instrument_id": instrument_id,
                "ts": int(time.time() * 1000),
                "side": signal_side,
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2),
                "size": 10.0, # Mock size
                "r": 1.5,
                "status": "pending_review",
                "reason": f"Breakout ({self.lookback} bars)",
                "meta": {"strategy": "breakout_v1"}
            }
        
        return None
