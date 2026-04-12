from __future__ import annotations

import asyncio
import logging

import orjson
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from redis.exceptions import RedisError

from core.config import settings
from core.events.bus import bus

logger = logging.getLogger(__name__)
router = APIRouter()


async def verify_stream_token(token: str = Query(default="")):
    """SSE can't set headers — check token from ?token= query param."""
    from core.config import settings as cfg

    if cfg.AUTH_TOKEN and token != cfg.AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


async def event_generator(request: Request):
    local_bus = None
    redis_available = True
    last_ping = 0.0

    try:
        local_bus = bus.redis.pubsub()
        await local_bus.subscribe(bus.channel)
        logger.debug("SSE subscribed to redis channel=%s", bus.channel)
    except RedisError as exc:
        redis_available = False
        logger.warning("SSE Redis subscribe failed: %s", exc, exc_info=True)
        if not settings.ALLOW_NO_REDIS:
            raise

    try:
        while True:
            if await request.is_disconnected():
                logger.debug("SSE client disconnected")
                break

            if redis_available and local_bus is not None:
                try:
                    message = await local_bus.get_message(ignore_subscribe_messages=True, timeout=1.0)
                except RedisError as exc:
                    logger.warning("SSE Redis read failed: %s", exc, exc_info=True)
                    if not settings.ALLOW_NO_REDIS:
                        raise
                    redis_available = False
                    message = None
                if message:
                    payload_raw = message.get("data")
                    payload_str = payload_raw if isinstance(payload_raw, str) else str(payload_raw)
                    try:
                        payload = orjson.loads(payload_str)
                        event_type = payload.get("type", "message")
                        yield f"event: {event_type}\ndata: {payload_str}\n\n"
                    except orjson.JSONDecodeError:
                        logger.warning("SSE dropped malformed payload: %r", payload_str)

            now = asyncio.get_running_loop().time()
            if now - last_ping >= max(2, int(settings.SSE_KEEPALIVE_SECONDS or 5)):
                heartbeat = orjson.dumps({"ts": int(now * 1000)}).decode("utf-8")
                yield f"event: heartbeat\ndata: {heartbeat}\n\n"
                last_ping = now

            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        logger.debug("SSE task cancelled")
        raise
    finally:
        if local_bus is not None:
            try:
                await local_bus.unsubscribe(bus.channel)
            except Exception:
                logger.debug("SSE unsubscribe skipped", exc_info=True)
            try:
                await local_bus.aclose()
            except Exception:
                logger.debug("SSE pubsub close skipped", exc_info=True)


@router.get("/stream", dependencies=[Depends(verify_stream_token)])
async def sse_stream(request: Request):
    headers = {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_generator(request), media_type="text/event-stream", headers=headers)
