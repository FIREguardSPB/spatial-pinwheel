"""
P3-03: MarketPublisher — throttled SSE candle publisher.

Responsible for:
  - Throttling kline publishes (max 1/s per instrument)
  - Building the SSE payload
"""
import asyncio

from core.events.bus import bus


class MarketPublisher:
    """Throttled publisher: sends at most one kline event per second per ticker."""

    def __init__(self, tf_str: str = "1m", throttle_sec: float = 1.0):
        self.tf_str = tf_str
        self.throttle_sec = throttle_sec
        self._last_sent: dict[str, float] = {}

    async def publish_candle(self, candle) -> None:
        """
        Publish kline SSE event if throttle window has elapsed.

        Args:
            candle: Candle namedtuple from CandleAggregator.
        """
        now = asyncio.get_running_loop().time()
        if now - self._last_sent.get(candle.instrument_id, 0) < self.throttle_sec:
            return

        payload = {
            "instrument_id": candle.instrument_id,
            "tf": self.tf_str,
            "candle": {
                "time": candle.time,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            },
        }
        await bus.publish("kline", payload)
        self._last_sent[candle.instrument_id] = now
