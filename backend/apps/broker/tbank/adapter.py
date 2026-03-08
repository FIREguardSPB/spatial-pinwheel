import sys
import asyncio
import logging
from pathlib import Path
from decimal import Decimal, ROUND_FLOOR
from typing import AsyncGenerator, Dict, List, Optional, Any
from datetime import datetime, timezone

import grpc
import httpx

# Add vendor/investapi/gen to sys.path to allow imports of generated code
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
GEN_DIR = BASE_DIR / "vendor" / "investapi" / "gen"
if str(GEN_DIR) not in sys.path:
    sys.path.append(str(GEN_DIR))

try:
    from google.protobuf.timestamp_pb2 import Timestamp
    import common_pb2  # noqa: F401
    import marketdata_pb2
    import marketdata_pb2_grpc
    import instruments_pb2
    import instruments_pb2_grpc
    import users_pb2
    import users_pb2_grpc
except ImportError as e:
    logging.getLogger(__name__).error(f"Failed to import gRPC modules: {e}")

logger = logging.getLogger(__name__)

_NANO = Decimal("1000000000")
PROD_ENDPOINT = "invest-public-api.tbank.ru:443"
SANDBOX_ENDPOINT = "sandbox-invest-public-api.tbank.ru:443"
REST_BASE_URL = "https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1"

_TRADING_STATUS_ALLOWED = {
    "SECURITY_TRADING_STATUS_NORMAL_TRADING",
    "SECURITY_TRADING_STATUS_SESSION_OPEN",
    "SECURITY_TRADING_STATUS_OPENING_PERIOD",
    "SECURITY_TRADING_STATUS_OPENING_AUCTION_PERIOD",
    "SECURITY_TRADING_STATUS_DEALER_NORMAL_TRADING",
    "SECURITY_TRADING_STATUS_TRADING_AT_CLOSING_AUCTION_PRICE",
}
_ORDER_STATUS_TERMINAL = {
    "EXECUTION_REPORT_STATUS_FILL",
    "EXECUTION_REPORT_STATUS_REJECTED",
    "EXECUTION_REPORT_STATUS_CANCELLED",
}


class TBankApiError(RuntimeError):
    pass


class TBankOrderRejected(TBankApiError):
    pass


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


def money_to_decimal(value: Optional[dict[str, Any]]) -> Decimal:
    if not value:
        return Decimal("0")
    units = Decimal(str(value.get("units", 0) or 0))
    nano = Decimal(str(value.get("nano", 0) or 0)) / _NANO
    return units + nano


def quotation_dict_to_decimal(value: Optional[dict[str, Any]]) -> Decimal:
    if not value:
        return Decimal("0")
    units = Decimal(str(value.get("units", 0) or 0))
    nano = Decimal(str(value.get("nano", 0) or 0)) / _NANO
    return units + nano


class TBankGrpcAdapter:
    def __init__(self, token: str, account_id: str, sandbox: bool = False):
        self.token = token
        self.account_id = account_id
        self.sandbox = sandbox
        self.target = SANDBOX_ENDPOINT if sandbox else PROD_ENDPOINT
        self.credentials = grpc.ssl_channel_credentials()
        self.metadata = (
            ("authorization", f"Bearer {token}"),
            ("x-app-name", "team.botpanel"),
        )
        self._channel = None
        self._figi_cache: Dict[str, str] = {}
        self._instrument_cache: Dict[str, dict[str, Any]] = {}

    async def _get_channel(self):
        if self._channel is None:
            self._channel = grpc.aio.secure_channel(self.target, self.credentials)
        return self._channel

    async def close(self):
        if self._channel:
            await self._channel.close()
            self._channel = None

    async def _rest_post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-app-name": "team.botpanel",
        }
        url = f"{REST_BASE_URL}/{method}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            detail = resp.text
            try:
                data = resp.json()
                detail = data.get("message") or data.get("description") or detail
            except Exception:
                pass
            raise TBankApiError(f"{method} failed with HTTP {resp.status_code}: {detail}")
        data = resp.json()
        if isinstance(data, dict) and data.get("code") and data.get("message"):
            raise TBankApiError(f"{method} failed: {data.get('message')} ({data.get('code')})")
        return data

    async def health_check(self) -> bool:
        try:
            await self.resolve_account_id(self.account_id or None)
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def get_accounts(self) -> list[dict[str, Any]]:
        data = await self._rest_post("UsersService/GetAccounts", {})
        return data.get("accounts", []) or []

    async def resolve_account_id(self, preferred_account_id: Optional[str] = None) -> str:
        accounts = await self.get_accounts()
        if not accounts:
            raise TBankApiError("No brokerage accounts available for the provided T-Bank token")

        def _is_live_usable(acc: dict[str, Any]) -> bool:
            return (
                acc.get("status") == "ACCOUNT_STATUS_OPEN"
                and acc.get("accessLevel") == "ACCOUNT_ACCESS_LEVEL_FULL_ACCESS"
            )

        if preferred_account_id:
            for account in accounts:
                if account.get("id") == preferred_account_id:
                    if not _is_live_usable(account):
                        raise TBankApiError(
                            f"T-Bank account {preferred_account_id} is not OPEN with FULL_ACCESS"
                        )
                    self.account_id = preferred_account_id
                    return preferred_account_id
            raise TBankApiError(f"Configured TBANK_ACCOUNT_ID {preferred_account_id} was not found")

        live_accounts = [acc for acc in accounts if _is_live_usable(acc)]
        if len(live_accounts) == 1:
            self.account_id = live_accounts[0]["id"]
            return self.account_id
        if not live_accounts:
            raise TBankApiError("No OPEN/FULL_ACCESS T-Bank accounts available for live trading")
        raise TBankApiError(
            "Multiple live T-Bank accounts available; specify TBANK_ACCOUNT_ID explicitly"
        )

    async def resolve_instrument(self, instrument_id: str) -> Optional[str]:
        details = await self.get_instrument_details(instrument_id)
        return details.get("uid") if details else None

    async def get_instrument_details(self, instrument_id: str) -> dict[str, Any]:
        if instrument_id in self._instrument_cache:
            return self._instrument_cache[instrument_id]

        if len(instrument_id) == 36 and "-" in instrument_id:
            query_value = instrument_id
        else:
            query_value = instrument_id.split(":")[-1]
        class_code = instrument_id.split(":")[0] if ":" in instrument_id else None

        found = await self._rest_post(
            "InstrumentsService/FindInstrument",
            {"query": query_value, "apiTradeAvailableFlag": True},
        )
        candidates = found.get("instruments", []) or []
        selected: Optional[dict[str, Any]] = None
        for item in candidates:
            if class_code and item.get("classCode") and item.get("classCode") != class_code:
                continue
            if item.get("ticker") == query_value or item.get("uid") == query_value or item.get("figi") == query_value:
                selected = item
                break
        if selected is None and candidates:
            selected = candidates[0]
        if selected is None:
            raise TBankApiError(f"Instrument not found via T-Bank API: {instrument_id}")

        instrument = await self._rest_post(
            "InstrumentsService/GetInstrumentBy",
            {"idType": "INSTRUMENT_ID_TYPE_UID", "id": selected.get("uid")},
        )
        payload = instrument.get("instrument") or {}
        details = {
            "uid": payload.get("uid") or selected.get("uid"),
            "figi": payload.get("figi") or selected.get("figi"),
            "ticker": payload.get("ticker") or selected.get("ticker"),
            "class_code": payload.get("classCode") or selected.get("classCode"),
            "name": payload.get("name") or selected.get("name"),
            "lot": int(payload.get("lot") or 1),
            "currency": payload.get("currency") or "RUB",
            "buy_available": bool(payload.get("buyAvailableFlag", True)),
            "sell_available": bool(payload.get("sellAvailableFlag", True)),
            "api_trade_available": bool(payload.get("apiTradeAvailableFlag", True)),
            "short_enabled": bool(payload.get("shortEnabledFlag", False)),
            "trading_status": payload.get("tradingStatus") or "SECURITY_TRADING_STATUS_UNSPECIFIED",
            "instrument_type": payload.get("instrumentType") or selected.get("instrumentType"),
            "min_price_increment": quotation_dict_to_decimal(payload.get("minPriceIncrement")),
        }
        self._instrument_cache[instrument_id] = details
        if details.get("uid"):
            self._figi_cache[instrument_id] = details["uid"]
        return details

    async def ensure_instrument_tradable(self, instrument_id: str, side: str) -> dict[str, Any]:
        details = await self.get_instrument_details(instrument_id)
        if not details.get("api_trade_available"):
            raise TBankApiError(f"Instrument {instrument_id} is not tradable via API")
        if side == "BUY" and not details.get("buy_available"):
            raise TBankApiError(f"Instrument {instrument_id} is not available for BUY orders")
        if side == "SELL" and not details.get("sell_available"):
            raise TBankApiError(f"Instrument {instrument_id} is not available for SELL orders")
        if details.get("trading_status") not in _TRADING_STATUS_ALLOWED:
            raise TBankApiError(
                f"Instrument {instrument_id} trading status does not allow market execution: {details.get('trading_status')}"
            )
        return details

    async def get_portfolio(self, account_id: Optional[str] = None) -> dict[str, Any]:
        acc_id = await self.resolve_account_id(account_id or self.account_id or None)
        return await self._rest_post("OperationsService/GetPortfolio", {"accountId": acc_id, "currency": "RUB"})

    async def get_positions(self, account_id: Optional[str] = None) -> dict[str, Any]:
        acc_id = await self.resolve_account_id(account_id or self.account_id or None)
        return await self._rest_post("OperationsService/GetPositions", {"accountId": acc_id})

    async def get_withdraw_limits(self, account_id: Optional[str] = None) -> dict[str, Any]:
        acc_id = await self.resolve_account_id(account_id or self.account_id or None)
        return await self._rest_post("OperationsService/GetWithdrawLimits", {"accountId": acc_id})

    async def post_market_order(
        self,
        *,
        instrument_id: str,
        quantity_lots: int,
        direction: str,
        order_id: str,
        account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        acc_id = await self.resolve_account_id(account_id or self.account_id or None)
        payload = {
            "instrumentId": instrument_id,
            "quantity": str(int(quantity_lots)),
            "direction": f"ORDER_DIRECTION_{direction}",
            "accountId": acc_id,
            "orderType": "ORDER_TYPE_MARKET",
            "orderId": order_id,
        }
        return await self._rest_post("OrdersService/PostOrder", payload)

    async def get_order_state(self, order_id: str, account_id: Optional[str] = None) -> dict[str, Any]:
        acc_id = await self.resolve_account_id(account_id or self.account_id or None)
        return await self._rest_post("OrdersService/GetOrderState", {"accountId": acc_id, "orderId": order_id})

    async def wait_for_terminal_order_state(
        self,
        *,
        order_id: str,
        timeout_sec: float,
        poll_interval_sec: float,
        account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout_sec
        last_state: Optional[dict[str, Any]] = None
        while asyncio.get_running_loop().time() < deadline:
            last_state = await self.get_order_state(order_id, account_id=account_id)
            status = last_state.get("executionReportStatus")
            if status in _ORDER_STATUS_TERMINAL:
                return last_state
            await asyncio.sleep(poll_interval_sec)
        raise TBankApiError(
            f"Order {order_id} did not reach terminal status within {timeout_sec:.1f}s"
        )

    async def get_candles(
        self, instrument_id: str, from_dt: datetime, to_dt: datetime, interval_str: str = "1m"
    ) -> List[Dict]:
        uid = await self.resolve_instrument(instrument_id)
        if not uid:
            return []

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
            figi=None,
            instrument_id=uid,
            from_=dt_to_timestamp(from_dt),
            to=dt_to_timestamp(to_dt),
            interval=grpc_interval,
        )

        try:
            resp = await stub.GetCandles(req, metadata=self.metadata)
            return [self._convert_candle(c, instrument_id, uid) for c in resp.candles]
        except Exception as e:
            logger.error(f"Error getting candles: {e}")
            return []

    async def stream_marketdata(self, instrument_ids: List[str]) -> AsyncGenerator[Dict, None]:
        backoff = 1
        while True:
            try:
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

                subscribe_req = marketdata_pb2.MarketDataRequest(
                    subscribe_candles_request=marketdata_pb2.SubscribeCandlesRequest(
                        subscription_action=marketdata_pb2.SUBSCRIPTION_ACTION_SUBSCRIBE,
                        instruments=[
                            marketdata_pb2.CandleInstrument(
                                instrument_id=uid,
                                interval=marketdata_pb2.SUBSCRIPTION_INTERVAL_ONE_MINUTE,
                            )
                            for uid in uids
                        ],
                    )
                )

                async def request_gen():
                    yield subscribe_req
                    while True:
                        await asyncio.sleep(3600)

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
                        pass
            except Exception as e:
                logger.error(f"Stream error: {e}. Reconnecting in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    def normalize_signal_qty_to_lots(self, qty_units: Decimal, lot_size: int) -> int:
        if lot_size <= 0:
            lot_size = 1
        lots = (qty_units / Decimal(lot_size)).to_integral_value(rounding=ROUND_FLOOR)
        return max(1, int(lots))

    def _convert_candle(self, c, instrument_id: str, broker_id: str) -> Dict:
        return {
            "instrument_id": instrument_id,
            "broker_id": broker_id,
            "time": int(c.time.timestamp()) if hasattr(c.time, "timestamp") else 0,
            "open": quotation_to_decimal(c.open),
            "high": quotation_to_decimal(c.high),
            "low": quotation_to_decimal(c.low),
            "close": quotation_to_decimal(c.close),
            "volume": c.volume,
            "is_complete": c.is_complete,
        }

    def _convert_stream_candle(self, c, instrument_id: str, broker_id: str) -> Dict:
        return {
            "instrument_id": instrument_id,
            "broker_id": broker_id,
            "time": int(c.time.timestamp()) if hasattr(c.time, "timestamp") else 0,
            "open": quotation_to_decimal(c.open),
            "high": quotation_to_decimal(c.high),
            "low": quotation_to_decimal(c.low),
            "close": quotation_to_decimal(c.close),
            "volume": c.volume,
            "event_type": "kline",
        }
