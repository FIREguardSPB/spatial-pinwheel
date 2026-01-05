from fastapi import APIRouter
from typing import List
from core.models.schemas import Candle

router = APIRouter()

@router.get("/{ticker}", response_model=List[Candle])
async def get_candles(ticker: str, tf: str = "15m"):
    from core.config import settings
    
    if settings.BROKER_PROVIDER == "tbank" and settings.TBANK_TOKEN:
        from apps.broker.tbank import TBankGrpcAdapter
        try:
            adapter = TBankGrpcAdapter(token=settings.TBANK_TOKEN, account_id=settings.TBANK_ACCOUNT_ID)
            # Fetch history
            from datetime import datetime, timedelta, timezone
            to_dt = datetime.now(timezone.utc)
            from_dt = to_dt - timedelta(days=1)
            
            candles = await adapter.get_candles(ticker, from_dt, to_dt, interval_str=tf)
            await adapter.close()
            
            # Ensure sorted explicitly for charts
            candles.sort(key=lambda x: x["time"])
            return candles
        except Exception as e:
            print(f"Error fetching candles from TBank: {e}")
            return []
            
    # Mock fallback
    import time
    import random
    
    # Generate 100 mock candles history
    mock_history = []
    end_ts = int(time.time())
    
    # Define timeframe duration in milliseconds
    tf_map = {
        "1m": 60,
        "5m": 5 * 60,
        "15m": 15 * 60,
        "1h": 60 * 60,
        "4h": 4 * 60 * 60,
        "1d": 24 * 60 * 60,
        "1w": 7 * 24 * 60 * 60,
    }
    
    step = tf_map.get(tf, 60) # Default to 1m
        
    start_ts = end_ts - (100 * step)
    
    current_price = 270.0 # base price
    
    for i in range(100):
        candle_ts = start_ts + (i * step)
        
        # Random walk
        change = (random.random() - 0.5) * (current_price * 0.002)
        close = current_price + change
        # Add some volatility based on TF
        volatility = (step / 60) * 0.05 # rough scaling
        
        open_p = current_price
        high = max(open_p, close) + random.random() * volatility
        low = min(open_p, close) - random.random() * volatility
        
        mock_history.append({
            "time": candle_ts,
            "open": round(open_p, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": int(random.random() * 1000)
        })
        current_price = close
        
    return mock_history
