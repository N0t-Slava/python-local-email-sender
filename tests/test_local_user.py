import pytest
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from src.configs.config import (
    LOCAL_USER_EMAIL,
    LOCAL_USER_ID,
    LOCAL_USER_NAME,
    LOCAL_USER_UNSUBSCRIBE_PUBLIC_KEY,
)
from src.main import app


@pytest.mark.asyncio
async def test_get_current_user_returns_configured_local_user():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        response = await ac.get("/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": LOCAL_USER_ID,
        "email": LOCAL_USER_EMAIL,
        "name": LOCAL_USER_NAME,
        "unsubscribe_public_key": LOCAL_USER_UNSUBSCRIBE_PUBLIC_KEY,
    }
