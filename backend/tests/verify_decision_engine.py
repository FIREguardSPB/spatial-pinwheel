import sys
import os
from decimal import Decimal
import logging

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from apps.worker.decision_engine.engine import DecisionEngine
from apps.worker.decision_engine.types import MarketSnapshot, Decision, ReasonCode
from apps.worker.decision_engine import indicators
from core.storage.models import Signal, Settings

# Mock Signal
def create_signal(side="BUY", entry=100.0, sl=95.0, tp=110.0):
    return Signal(
        side=side,
        entry=Decimal(str(entry)),
        sl=Decimal(str(sl)),
        tp=Decimal(str(tp)),
        size=Decimal("1.0"),
        status="pending_review",
        instrument_id="TEST"
    )

def create_candles(n, start_price=100.0):
    candles = []
    price = start_price
    for i in range(n):
        # Fake trend up
        price += 0.1
        candles.append({
            "close": Decimal(str(price)),
            "high": Decimal(str(price + 0.5)),
            "low": Decimal(str(price - 0.5)),
            "time": 1000 + i*60,
            "volume": 100
        })
    return candles

def test_hard_reject_no_data():
    print("Test 1: Hard Reject (No Data)... ", end="")
    settings = Settings()
    engine = DecisionEngine(settings)
    
    # 10 candles < 50
    snapshot = MarketSnapshot(candles=create_candles(10), last_price=Decimal("100"))
    signal = create_signal()
    
    result = engine.evaluate(signal, snapshot)
    
    if result.decision == Decision.REJECT and result.reasons[0].code == ReasonCode.NO_MARKET_DATA:
        print("PASS")
    else:
        print(f"FAIL: {result.decision} {result.reasons}")

def test_idempotency():
    print("Test 2: Idempotency... ", end="")
    settings = Settings()
    engine = DecisionEngine(settings)
    
    snapshot = MarketSnapshot(candles=create_candles(200), last_price=Decimal("120"))
    signal = create_signal(entry=120, sl=118, tp=125)
    
    res1 = engine.evaluate(signal, snapshot)
    res2 = engine.evaluate(signal, snapshot)
    
    if res1.score == res2.score and len(res1.reasons) == len(res2.reasons):
        print("PASS")
    else:
        print(f"FAIL: {res1.score} vs {res2.score}")

def test_scoring_logic():
    print("Test 3: Scoring Logic... ", end="")
    settings = Settings()
    engine = DecisionEngine(settings)
    
    # Uptrend candles
    candles = create_candles(200, start_price=100)
    # Last price ~120. 
    # EMA50 will be below price (Bullish).
    # RSI likely stable high.
    
    signal = create_signal(side="BUY", entry=120, sl=118, tp=130)
    snapshot = MarketSnapshot(candles=candles, last_price=Decimal("120"))
    
    result = engine.evaluate(signal, snapshot)
    
    # Expect Regimate Match (+20)
    # ATR ~1.0 (High-Low=1.0). SL Dist = 2.0. SL/ATR = 2.0. Good Volatility +15.
    # Level: Max High is ~120.5. TP 130. Ratio? 
    
    if result.score > 0:
        print(f"PASS (Score {result.score})")
    else:
        print(f"FAIL (Score {result.score})")
        for r in result.reasons:
            print(r)

if __name__ == "__main__":
    test_hard_reject_no_data()
    test_idempotency()
    test_scoring_logic()
