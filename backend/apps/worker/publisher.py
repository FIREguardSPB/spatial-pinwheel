"""
P3-03: MarketPublisher — throttled SSE candle publisher.

Responsible for:
  - Throttling kline publishes (max 1/s per instrument)
  - Building the SSE payload
  - Emitting heartbeat republishes so the chart keeps moving even when
    sandbox candles do not change materially between polls.
"""
import asyncio
import logging

from core.events.bus import bus

logger = logging.getLogger(__name__)


class MarketPublisher:
    """Throttled publisher: sends at most one kline event per second per ticker.

    Additionally, if the candle payload is identical to the previous one, it will
    still be re-published every ``heartbeat_sec`` seconds. This keeps SSE-driven
    charts alive in low-activity sandbox conditions where price and volume can stay
    unchanged for multiple poll cycles.
    """

    def __init__(self, tf_str: str = "1m", throttle_sec: float = 1.0, heartbeat_sec: float = 10.0):
        self.tf_str = tf_str
        self.throttle_sec = throttle_sec
        self.heartbeat_sec = heartbeat_sec
        self._last_sent: dict[str, float] = {}
        self._last_payload: dict[str, tuple] = {}
        self._last_forced: dict[str, float] = {}

    async def publish_candle(self, candle) -> None:
        now = asyncio.get_running_loop().time()
        instrument_id = candle.instrument_id
        payload_key = (
            candle.time,
            str(candle.open),
            str(candle.high),
            str(candle.low),
            str(candle.close),
            int(candle.volume),
        )
        last_key = self._last_payload.get(instrument_id)
        is_same_payload = last_key == payload_key

        if now - self._last_sent.get(instrument_id, 0) < self.throttle_sec:
            return

        if is_same_payload and now - self._last_forced.get(instrument_id, 0) < self.heartbeat_sec:
            return

        payload = {
            "instrument_id": instrument_id,
            "tf": self.tf_str,
            "candle": {
                "time": candle.time,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            },
            "heartbeat": is_same_payload,
        }
        await bus.publish("kline", payload)
        self._last_sent[instrument_id] = now
        self._last_payload[instrument_id] = payload_key
        if is_same_payload:
            self._last_forced[instrument_id] = now
            logger.debug("publish_candle heartbeat %s tf=%s t=%s", instrument_id, self.tf_str, candle.time)
        else:
            logger.debug("publish_candle %s tf=%s t=%s", instrument_id, self.tf_str, candle.time)
