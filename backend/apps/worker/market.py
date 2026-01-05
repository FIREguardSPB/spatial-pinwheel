import time
import random

class MarketGenerator:
    def __init__(self, tickers: list[str]):
        self.tickers = tickers
        self.prices = {t: 270.0 for t in tickers} # Start price
        self.candles = {t: [] for t in tickers}

    def generate_tick(self) -> dict:
        """
        Simulates a tick/candle close update.
        For MVP, returns a finalized candle every call (fast replay) or mock real-time.
        Let's assume this is called every 1s, and every 5s we 'close' a candle for speed.
        """
        updates = {}
        ts = int(time.time())
        
        for t in self.tickers:
            current = self.prices[t]
            change = (random.random() - 0.5) * (current * 0.002) # 0.2% volatility
            close = current + change
            self.prices[t] = close
            
            # Simple candle
            open_p = current
            high = max(open_p, close) + random.random() * 0.1
            low = min(open_p, close) - random.random() * 0.1
            
            candle = {
                "time": ts,
                "open": round(open_p, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": int(random.random() * 1000)
            }
            
            updates[t] = candle
            # Append to history for strategy
            self.candles[t].append(candle)
            if len(self.candles[t]) > 50: self.candles[t].pop(0)
            
        return updates
