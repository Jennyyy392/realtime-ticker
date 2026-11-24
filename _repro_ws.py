import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.api.v1.dependencies import check_rate_limit
from app.services.broadcaster import broadcaster


class IdlePubSub:
    async def subscribe(self, channel):
        return None

    async def unsubscribe(self, channel):
        return None

    async def aclose(self):
        return None

    async def get_message(self, ignore_subscribe_messages=True, timeout=1.0):
        await asyncio.sleep(0.05)
        return None


class FakeRedis:
    def pubsub(self):
        return IdlePubSub()


pipe = MagicMock()
pipe.execute = AsyncMock()
cm = MagicMock()
cm.__aenter__ = AsyncMock(return_value=pipe)
cm.__aexit__ = AsyncMock(return_value=False)
fake_redis = AsyncMock()
fake_redis.ping = AsyncMock(return_value=True)
fake_redis.pipeline = MagicMock(return_value=cm)

app.dependency_overrides[check_rate_limit] = lambda: None

with patch("app.main.redis_client", fake_redis), \
        patch("app.redis_client.redis_client", fake_redis), \
        patch.object(broadcaster, "_redis", FakeRedis()):
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/prices") as ws:
            print("connected")
print("OK")