import sys
import os
import time
from decimal import Decimal

# Add backend to path
sys.path.append(os.getcwd())

from core.storage.session import SessionLocal
from core.storage.models import Settings
from core.storage.repos import signals as signal_repo
from apps.worker.decision_engine.engine import DecisionEngine
from apps.worker.decision_engine.types import MarketSnapshot


def verify():
    print("Verifying Decision Engine Integration...")
    db = SessionLocal()

    # 1. Get Settings
    settings = db.query(Settings).first()
    if not settings:
        print("ERROR: No Settings found.")
        return

    print(f"Settings Loaded: RR_Min={settings.rr_min}")

    # 2. Create Engine
    engine = DecisionEngine(settings)

    # 3. Create Fake Signal
    sig_data = {
        "instrument_id": "TQBR:INTEG",
        "ts": int(time.time()),
        "side": "BUY",
        "entry": 270.0,
        "sl": 260.0,
        "tp": 290.0,
        "size": 10,
        "r": 2.0,
        "reason": "Integration Test",
        "meta": {"strategy": "audit_script"},
    }
    signal = signal_repo.create_signal(db, sig_data)
    print(f"Signal Created: {signal.id}")

    # 4. Create Snapshot (Uptrend for MACD positive)
    candles = []
    base = 250.0
    for i in range(60):
        c = {
            "time": int(time.time()) - (60 - i) * 60,
            "open": base,
            "high": base + 5,
            "low": base - 5,
            "close": base + 1,
            "volume": 1000,
        }
        candles.append(c)
        base += 0.5

    snapshot = MarketSnapshot(candles=candles, last_price=Decimal(280.0))

    # 5. Evaluate
    res = engine.evaluate(signal, snapshot)
    print(f"Evaluation Result: {res.decision} Score:{res.score}")
    print(f"Metrics: {res.metrics}")

    # 6. Save (Simulate Worker)
    meta = dict(signal.meta)
    meta["decision"] = res.model_dump(mode="json")
    signal.meta = meta
    db.commit()
    print("Saved to DB.")


if __name__ == "__main__":
    verify()
