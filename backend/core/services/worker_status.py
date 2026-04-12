from __future__ import annotations

import time
from typing import Any

import orjson

from core.events.bus import bus

WORKER_STATUS_KEY = "spatial_pinwheel:worker_status"
WORKER_STATUS_TTL_SEC = 300


def _now_ms() -> int:
    return int(time.time() * 1000)


async def publish_worker_status(payload: dict[str, Any]) -> None:
    body = dict(payload)
    body.setdefault("updated_ts", _now_ms())
    await bus.redis.set(WORKER_STATUS_KEY, orjson.dumps(body).decode(), ex=WORKER_STATUS_TTL_SEC)


async def read_worker_status() -> dict[str, Any]:
    raw = await bus.redis.get(WORKER_STATUS_KEY)
    if not raw:
        return {
            "ok": False,
            "phase": "offline",
            "message": "Worker status is unavailable",
            "updated_ts": None,
        }
    try:
        data = orjson.loads(raw)
        if isinstance(data, dict):
            data.setdefault("ok", True)
            return data
    except Exception:
        pass
    return {
        "ok": False,
        "phase": "error",
        "message": "Worker status payload is invalid",
        "updated_ts": None,
    }
