import asyncio
import orjson
from decimal import Decimal
from typing import Dict, List
from core.events.bus import bus
from core.storage.session import SessionLocal
from core.strategy.breakout import BreakoutStrategy
from core.execution.paper import PaperExecutionEngine
from apps.worker.market import MarketGenerator
from core.storage.models import Signal, DecisionLog
from core.storage.repos import signals as signal_repo
from apps.worker.decision_engine.engine import DecisionEngine
from apps.worker.decision_engine.types import MarketSnapshot, Decision
from collections import deque
import uuid
import time
import os

async def run_worker():
    print("Worker starting...")
    tf_str = os.getenv("TF", "1m")
    print(f"Worker Timeframe: {tf_str}")
    
    # helper for frame seconds (standardized)
    if tf_str == "1m":
        frame_sec = 60
    elif tf_str == "5m":
        frame_sec = 5 * 60
    elif tf_str == "15m":
        frame_sec = 15 * 60
    else:
        frame_sec = 60 # default 1m
    db = SessionLocal()
    
    # Configuration
    from core.config import settings
    tickers = ["TQBR:SBER", "TQBR:GAZP", "TQBR:LKOH"]
    
    # Components
    strategy = BreakoutStrategy(lookback=5)
    execution = PaperExecutionEngine(db)
    decision_engine = DecisionEngine(settings)
    
    # State for Aggregation (OHLCV Builder)
    # Map: ticker -> current_15m_candle (dict)
    current_candles: Dict[str, dict] = {} 
    last_sent_time: Dict[str, float] = {} # For throttling
    
    # History Buffer for Decision Engine (Need ~200 candles)
    # History Buffer for Decision Engine (Need ~200 candles)
    # Map: ticker -> deque of completed candles
    history: Dict[str, deque] = {t: deque(maxlen=200) for t in tickers}
    
    # Adapter / Generator
    market_stream = None
    if settings.BROKER_PROVIDER == "tbank" and settings.TBANK_TOKEN:
        print(f"Using T-Bank Adapter (gRPC) [Sandbox={settings.TBANK_SANDBOX}]...")
        from apps.broker.tbank import TBankGrpcAdapter
        adapter = TBankGrpcAdapter(token=settings.TBANK_TOKEN, account_id=settings.TBANK_ACCOUNT_ID, sandbox=settings.TBANK_SANDBOX)
        
        # NOTE: For v1 we skip pre-filling history to avoid startup delay/complexity, 
        # but DecisionEngine will REJECT first ~50 signals until history builds up.
        
        market_stream = adapter.stream_marketdata(tickers)
    else:
        print("Using Mock Market Generator...")
        market = MarketGenerator(tickers=tickers)
        
        # Wrap mock in an async generator to unify interface
        async def mock_stream():
            while True:
                updates = market.generate_tick()
                for t, c in updates.items():
                    # Mock produces 'completed' candles, but we treat them as stream updates
                    yield {
                        "instrument_id": t,
                        "broker_id": None,
                        "time": c["time"], # MS in Mock? Need to check. Assuming MS from old code match
                        "open": Decimal(str(c['open'])),
                        "high": Decimal(str(c['high'])),
                        "low": Decimal(str(c['low'])),
                        "close": Decimal(str(c['close'])),
                        "volume": c['volume'],
                        "is_complete": False # Continuous updates
                    }
                await asyncio.sleep(1.0)
        market_stream = mock_stream()

    # Redis Command Subscriber
    cmd_pubsub = bus.redis.pubsub()
    await cmd_pubsub.subscribe("cmd:execute_signal")
    
    # Process Loop
    print("Worker running loops...")
    last_signal_check = 0
    signal_interval = 60 # Check signals every 1m? Or on every tick?
                         # Strategy usually runs on close.
                         # We check on every tick if candle closed?
    
    # We need a robust loop. For MVP:
    # We iterate properly async
    command_task = asyncio.create_task(command_listener(cmd_pubsub, execution))
    print("Command listener started")
    
    try:
        async for tick in market_stream:
            # tick is a dict: { instrument_id, ts, open, high, low, close, volume } (Decimals)
            ticker = tick["instrument_id"]
            
            # --- OHLCV Aggregation (1m/Tick -> 15m) ---
            # Standardize Time: If tick time > 3000000000 (likely MS), convert to Seconds?
            # Unix Sec now ~1.7e9. MS ~1.7e12.
            tick_time = tick["time"]
            if tick_time > 10000000000:
                 tick_time = int(tick_time / 1000)
            
            # 1. Determine start of candle for this tick
            current_frame_start = (tick_time // frame_sec) * frame_sec
            
            # 2. Get or Initialize current candle
            candle = current_candles.get(ticker)
            
            if not candle or candle["time"] != current_frame_start:
                # New bar started
                if candle:
                    # Finalize previous candle
                    # Add to history
                    history[ticker].append({
                        "time": candle["time"],
                        "open": candle["open"],
                        "high": candle["high"],
                        "low": candle["low"],
                        "close": candle["close"],
                        "volume": candle["volume"]
                    })
                    
                candle = {
                    "instrument_id": ticker,
                    "time": current_frame_start,
                    "open": tick["open"],
                    "high": tick["high"],
                    "low": tick["low"],
                    "close": tick["close"],
                    "volume": tick["volume"],
                    "is_complete": False
                }
            else:
                # Update existing bar
                candle["high"] = max(candle["high"], tick["high"])
                candle["low"] = min(candle["low"], tick["low"])
                candle["close"] = tick["close"]
                candle["volume"] += tick["volume"] # Accumulate volume
            
            current_candles[ticker] = candle
            
            # --- Throttling (1s) ---
            now_ts = asyncio.get_event_loop().time()
            last_ts = last_sent_time.get(ticker, 0)
            
            if now_ts - last_ts > 1.0:
                payload = {
                    "instrument_id": ticker,
                    "tf": tf_str,
                    "candle": {
                        "time": candle["time"],
                        "open": float(candle["open"]),
                        "high": float(candle["high"]),
                        "low": float(candle["low"]),
                        "close": float(candle["close"]),
                        "volume": int(candle["volume"])
                    }
                }
                await bus.publish("kline", payload)
                last_sent_time[ticker] = now_ts
                
            # --- Strategy & Decision Check ---
            if now_ts - last_signal_check > signal_interval:
                last_signal_check = now_ts
                
                # Check Strategy
                # Use current candle as "latest"
                simulated_history = [{
                    "time": candle["time"], 
                    "open": float(candle["open"]),
                    "high": float(candle["high"]),
                    "low": float(candle["low"]),
                    "close": float(candle["close"]),
                    "volume": int(candle["volume"])
                }]
                
                sig_data = strategy.analyze(ticker, simulated_history)
                
                if sig_data:
                    pending_count = signal_repo.count_pending_signals(db, ticker)
                    if pending_count == 0:
                        try:
                            # 1. Create Signal (Pending Review)
                            # Persist Signal first
                            signal_orm = signal_repo.create_signal(db, sig_data)
                            
                            # 2. Decision Engine Evaluate
                            # Construct Snapshot
                            # Use History + Current Candle
                            snapshot_candles = list(history[ticker])
                            # Add current partial candle for up-to-date analysis
                            snapshot_candles.append({
                                "time": candle["time"],
                                "open": candle["open"],
                                "high": candle["high"],
                                "low": candle["low"],
                                "close": candle["close"],
                                "volume": candle["volume"]
                            })
                            
                            snapshot = MarketSnapshot(
                                candles=snapshot_candles,
                                last_price=candle["close"]
                            )
                            
                            evaluation = decision_engine.evaluate(signal_orm, snapshot)
                            
                            # 3. Update Signal with Decision
                            meta = dict(signal_orm.meta) if signal_orm.meta else {}
                            meta["decision"] = evaluation.model_dump(mode='json')
                            signal_orm.meta = meta
                            db.commit()
                            
                            # 4. Log Decision
                            log_entry = DecisionLog(
                                id=str(uuid.uuid4()),
                                ts=int(time.time()), # Seconds
                                type="decision_engine",
                                message=f"{evaluation.decision.value} {ticker} {sig_data['meta'].get('strategy', 'unknown')}",
                                payload=evaluation.model_dump(mode='json')
                            )
                            db.add(log_entry)
                            db.commit()
                            
                            # 5. Notify UI
                            await bus.publish("signal_updated", {
                                "id": signal_orm.id, 
                                "status": signal_orm.status,
                                "meta": meta
                            })
                            print(f"Signal Evaluated: {ticker} -> {evaluation.decision.value} (Score {evaluation.score})")
                            
                            # 6. Auto Execution Checks
                            trade_mode = getattr(settings, "trade_mode", "review")
                            # If TAKE and Auto Paper/Live
                            if evaluation.decision == Decision.TAKE:
                                if trade_mode == "auto_paper":
                                    print(f"Auto-Executing {signal_orm.id} (PAPER)")
                                    # Approve
                                    signal_repo.update_signal_status(db, signal_orm.id, "approved")
                                    # Execute
                                    await execution.execute_approved_signal(signal_orm.id)
                                    
                        except Exception as e:
                            print(f"Error processing signal/decision: {e}")
                            import traceback
                            traceback.print_exc()

    except Exception as e:
        print(f"Worker Loop Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        command_task.cancel()
        db.close()
        
async def command_listener(pubsub, execution):
    print("Command listener started")
    while True:
        try:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg:
                data = orjson.loads(msg['data'])
                sig_id = data.get("signal_id")
                print(f"Received Execution Command for {sig_id}")
                if sig_id:
                    await execution.execute_approved_signal(sig_id)
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Command Error: {e}")
            await asyncio.sleep(1.0)

if __name__ == "__main__":
    asyncio.run(run_worker())
