"""Tests de los healthchecks. No tocan base de datos ni red."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


async def test_healthz_is_ok(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_is_ok_when_database_responds(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def database_up() -> bool:
        return True

    monkeypatch.setattr("app.main.ping_database", database_up)

    response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


async def test_readyz_is_unavailable_when_database_is_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def database_down() -> bool:
        return False

    monkeypatch.setattr("app.main.ping_database", database_down)

    response = await client.get("/readyz")

    assert response.status_code == 503
