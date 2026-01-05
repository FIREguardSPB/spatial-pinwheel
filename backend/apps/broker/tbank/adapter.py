import sys
import os
import asyncio
import logging
from pathlib import Path
from decimal import Decimal, ROUND_FLOOR
from typing import AsyncGenerator, Dict, List, Optional, Tuple
from datetime import datetime, timezone

import grpc

# Add vendor/investapi/gen to sys.path to allow imports of generated code
# This file is in backend/apps/broker/tbank/adapter.py
# Gen dir is backend/vendor/investapi/gen
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
GEN_DIR = BASE_DIR / "vendor" / "investapi" / "gen"
if str(GEN_DIR) not in sys.path:
    sys.path.append(str(GEN_DIR))

try:
    from google.protobuf.timestamp_pb2 import Timestamp
    import common_pb2
    import marketdata_pb2
    import marketdata_pb2_grpc
    import instruments_pb2
    import instruments_pb2_grpc
    import users_pb2
    import users_pb2_grpc
except ImportError as e:
    # Log error but don't crash at import time if possible, 
    # though usage will fail.
    logging.getLogger(__name__).error(f"Failed to import gRPC modules: {e}")

logger = logging.getLogger(__name__)

_NANO = Decimal("1000000000")
PROD_ENDPOINT = "invest-public-api.tbank.ru:443"
SANDBOX_ENDPOINT = "sandbox-invest-public-api.tbank.ru:443"

def quotation_to_decimal(q) -> Decimal:
    if not q:
        return Decimal("0")
    return Decimal(q.units) + (Decimal(q.nano) / _NANO)

def decimal_to_quotation(x: Decimal):
    units = int(x)
    nano = int((x - Decimal(units)) * _NANO)
    return units, nano

def now_timestamp() -> Timestamp:
    ts = Timestamp()
    ts.GetCurrentTime()
    return ts

def dt_to_timestamp(dt: datetime) -> Timestamp:
    ts = Timestamp()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts.FromDatetime(dt)
    return ts

class TBankGrpcAdapter:
    def __init__(self, token: str, account_id: str, sandbox: bool = False):
        self.token = token
        self.account_id = account_id
        self.target = SANDBOX_ENDPOINT if sandbox else PROD_ENDPOINT
        self.credentials = grpc.ssl_channel_credentials()
        self.metadata = (
            ("authorization", f"Bearer {token}"),
            ("x-app-name", "team.botpanel"),
        )
        self._channel = None
        self._figi_cache: Dict[str, str] = {} # instrument_id (ticker) -> uid

    async def _get_channel(self):
        if self._channel is None:
            self._channel = grpc.aio.secure_channel(self.target, self.credentials)
        return self._channel

    async def close(self):
        if self._channel:
            await self._channel.close()
            self._channel = None

    async def health_check(self) -> bool:
        try:
            channel = await self._get_channel()
            stub = users_pb2_grpc.UsersServiceStub(channel)
            await stub.GetAccounts(users_pb2.GetAccountsRequest(), metadata=self.metadata)
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def resolve_instrument(self, instrument_id: str) -> Optional[str]:
        """
        Resolves UI instrument_id (e.g. SBER) to instrument_uid.
        Uses InstrumentsService.
        """
        if instrument_id in self._figi_cache:
            return self._figi_cache[instrument_id]
        
        # Handle compound ID if needed (e.g. TQBR:SBER)
        # For simplicity assume input is Ticker or UID.
        # Check if it looks like a UID (len 36?)
        if len(instrument_id) == 36 and "-" in instrument_id:
            return instrument_id

        ticker = instrument_id.split(":")[-1] # Remove prefix if any
        class_code = instrument_id.split(":")[0] if ":" in instrument_id else None

        try:
            channel = await self._get_channel()
            stub = instruments_pb2_grpc.InstrumentsServiceStub(channel)
            
            # Use FindInstrument
            req = instruments_pb2.FindInstrumentRequest(query=ticker)
            resp = await stub.FindInstrument(req, metadata=self.metadata)
            
            for item in resp.instruments:
                if item.ticker == ticker:
                    # Prefer share if multiple
                    # Or match class_code if provided
                    if class_code and item.class_code != class_code:
                        continue
                        
                    self._figi_cache[instrument_id] = item.uid
                    return item.uid
            
            # If strictly not found
            logger.warning(f"Instrument not found for ticker: {ticker}")
            return None
            
        except Exception as e:
            logger.error(f"Error resolving instrument {instrument_id}: {e}")
            return None

    async def get_candles(self, instrument_id: str, from_dt: datetime, to_dt: datetime, interval_str: str = "1m") -> List[Dict]:
        uid = await self.resolve_instrument(instrument_id)
        if not uid:
            return []
            
        # Map interval. P0: support 1m, 15m.
        # CandleInterval enum: 
        # CANDLE_INTERVAL_1_MIN = 1
        # CANDLE_INTERVAL_5_MIN = 2
        # CANDLE_INTERVAL_15_MIN = 3
        # ...
        interval_map = {
            "1m": marketdata_pb2.CANDLE_INTERVAL_1_MIN,
            "5m": marketdata_pb2.CANDLE_INTERVAL_5_MIN,
            "15m": marketdata_pb2.CANDLE_INTERVAL_15_MIN,
            "1h": marketdata_pb2.CANDLE_INTERVAL_HOUR,
            "1d": marketdata_pb2.CANDLE_INTERVAL_DAY,
        }
        grpc_interval = interval_map.get(interval_str, marketdata_pb2.CANDLE_INTERVAL_1_MIN)
        
        channel = await self._get_channel()
        stub = marketdata_pb2_grpc.MarketDataServiceStub(channel)
        
        req = marketdata_pb2.GetCandlesRequest(
            figi=None, # Deprecated
            instrument_id=uid,
            from_=dt_to_timestamp(from_dt),
            to=dt_to_timestamp(to_dt),
            interval=grpc_interval
        )
        
        try:
            resp = await stub.GetCandles(req, metadata=self.metadata)
            return [self._convert_candle(c, instrument_id, uid) for c in resp.candles]
        except Exception as e:
            logger.error(f"Error getting candles: {e}")
            return []

    async def stream_marketdata(self, instrument_ids: List[str]) -> AsyncGenerator[Dict, None]:
        """
        Bidirectional stream for candles.
        Retries connection on failure.
        """
        backoff = 1
        
        while True:
            try:
                # Resolve all UIDs
                uids = []
                map_uid_ticker = {}
                for iid in instrument_ids:
                    uid = await self.resolve_instrument(iid)
                    if uid:
                        uids.append(uid)
                        map_uid_ticker[uid] = iid
                
                if not uids:
                    logger.warning("No instruments resolved for streaming.")
                    await asyncio.sleep(5)
                    continue

                channel = await self._get_channel()
                stub = marketdata_pb2_grpc.MarketDataStreamServiceStub(channel)
                
                # Initial subscription request
                # We want 1-minute candles for now
                subscribe_req = marketdata_pb2.MarketDataRequest(
                    subscribe_candles_request=marketdata_pb2.SubscribeCandlesRequest(
                        subscription_action=marketdata_pb2.SUBSCRIPTION_ACTION_SUBSCRIBE,
                        instruments=[
                            marketdata_pb2.CandleInstrument(
                                instrument_id=uid,
                                interval=marketdata_pb2.SUBSCRIPTION_INTERVAL_ONE_MINUTE
                            ) for uid in uids
                        ]
                    )
                )
                
                # Request generator
                async def request_gen():
                    yield subscribe_req
                    # Keep loop open? Protocol says we send sub requests, then listen.
                    # We usually don't send anything else unless changing subs.
                    # But if we return, the stream might close from client side? 
                    # Usually we yield requests as needed. Here just one.
                    # Wait forever or until needed.
                    # Actually, for bidirectional, if we finish yielding, does it close unrelated to receiving?
                    # Typically yes. So we should hang here or yield heatbeats if needed (T-Bank has server-side pings).
                    # We can await a future that is cancelled on exception.
                    while True:
                        await asyncio.sleep(3600) # Sleep forever

                stream = stub.MarketDataStream(request_gen(), metadata=self.metadata)
                
                logger.info(f"Connected to T-Bank stream for {len(uids)} instruments.")
                backoff = 1
                
                async for resp in stream:
                    if resp.HasField("candle"):
                        c = resp.candle
                        internal_id = map_uid_ticker.get(c.instrument_uid)
                        if internal_id:
                            yield self._convert_stream_candle(c, internal_id, c.instrument_uid)
                    elif resp.HasField("ping"):
                        # Auto-response might not be needed if using unary-stream style, 
                        # but it's bidirectional. Server sends ping, client should maybe respond?
                        # T-Bank doc says: "Server sends ping... Client should send nothing?"
                        # Actually T-Bank sends Ping and expects nothing usually, checking keepalive via TCP.
                        pass
                        
            except Exception as e:
                logger.error(f"Stream error: {e}. Reconnecting in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
                # Force channel recreation on error?
                # Sometimes channel enters bad state.
                # await self.close() 

    def _convert_candle(self, c, instrument_id: str, broker_id: str) -> Dict:
        return {
            "instrument_id": instrument_id,
            "broker_id": broker_id,
            "time": int(c.time.timestamp()) if hasattr(c.time, 'timestamp') else 0, # Standard: Unix Seconds
            "open": quotation_to_decimal(c.open),
            "high": quotation_to_decimal(c.high),
            "low": quotation_to_decimal(c.low),
            "close": quotation_to_decimal(c.close),
            "volume": c.volume,
            "is_complete": c.is_complete
        }

    def _convert_stream_candle(self, c, instrument_id: str, broker_id: str) -> Dict:
        # Stream candle structure is different? usually similar but maybe wrapped.
        # c is Candle message from marketdata.proto
        return {
            "instrument_id": instrument_id,
            "broker_id": broker_id,
            "time": int(c.time.timestamp()) if hasattr(c.time, 'timestamp') else 0, # Standard: Unix Seconds
            "open": quotation_to_decimal(c.open),
            "high": quotation_to_decimal(c.high),
            "low": quotation_to_decimal(c.low),
            "close": quotation_to_decimal(c.close),
            "volume": c.volume,
            "event_type": "kline"
        }

