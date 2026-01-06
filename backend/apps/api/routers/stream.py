from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from core.events.bus import bus
from core.config import settings
import asyncio
import orjson

router = APIRouter()


async def event_generator():
    local_bus = bus.redis.pubsub()
    await local_bus.subscribe(bus.channel)

    try:
        last_ping = 0.0

        while True:
            # Check for message with short timeout to allow loop to run
            message = await local_bus.get_message(ignore_subscribe_messages=True, timeout=1.0)

            if message:
                payload_str = message["data"]
                try:
                    payload = orjson.loads(payload_str)
                    event_type = payload.get("type", "message")
                    yield f"event: {event_type}\ndata: {payload_str}\n\n"
                except orjson.JSONDecodeError:
                    pass  # Ignore bad JSON

            # Keepalive logic
            now = asyncio.get_event_loop().time()
            if now - last_ping > settings.SSE_KEEPALIVE_SECONDS:
                yield ": ping\n\n"
                last_ping = now

            await asyncio.sleep(0.1)

    except asyncio.CancelledError:
        await local_bus.unsubscribe(bus.channel)


@router.get("/stream")
async def sse_stream():
    return StreamingResponse(event_generator(), media_type="text/event-stream")
