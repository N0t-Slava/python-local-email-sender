import pytest
from redis.asyncio import Redis


@pytest.mark.asyncio
async def test_redis():
    r = Redis.from_url("redis://127.0.0.1:6380/0")
    pong = await r.ping()
    print("Redis connected:", pong)
    await r.close()
