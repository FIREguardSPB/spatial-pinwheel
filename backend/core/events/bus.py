import redis.asyncio as redis
from core.config import settings
import orjson
import time


class EventBus:
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        self.channel = "events:v1"

    async def publish(self, type: str, data: dict):
        """
        Publishes a unified event: {type, ts, data}
        """
        payload = {"type": type, "ts": int(time.time() * 1000), "data": data}
        await self.redis.publish(self.channel, orjson.dumps(payload).decode())

    async def subscribe(self):
        await self.pubsub.subscribe(self.channel)
        return self.pubsub

    async def get_message(self):
        return await self.pubsub.get_message(ignore_subscribe_messages=True)

    async def close(self):
        await self.redis.close()


# Global bus instance (users should use dependency injection or context manager in real app, singleton ok for MVP)
bus = EventBus()
