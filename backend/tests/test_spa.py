"""Servido de la SPA construida (D4). No toca base de datos ni red."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text("<!doctype html><title>index</title>", encoding="utf-8")
    (tmp_path / "200.html").write_text("<!doctype html><title>fallback</title>", encoding="utf-8")
    (tmp_path / "_app").mkdir()
    (tmp_path / "_app" / "app.js").write_text("console.log('hi')", encoding="utf-8")
    return tmp_path


@pytest.fixture
async def spa_client(dist_dir: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    monkeypatch.setenv("FRONTEND_DIST_DIR", str(dist_dir))
    get_settings.cache_clear()
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    get_settings.cache_clear()


async def test_root_serves_index(spa_client: AsyncClient) -> None:
    response = await spa_client.get("/")

    assert response.status_code == 200
    assert "index" in response.text


async def test_unknown_route_serves_fallback(spa_client: AsyncClient) -> None:
    response = await spa_client.get("/web/42")

    assert response.status_code == 200
    assert "fallback" in response.text


async def test_asset_is_served(spa_client: AsyncClient) -> None:
    response = await spa_client.get("/_app/app.js")

    assert response.status_code == 200
    assert "console.log" in response.text


async def test_unknown_api_route_is_404_not_shell(spa_client: AsyncClient) -> None:
    response = await spa_client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert "fallback" not in response.text


async def test_healthz_still_works(spa_client: AsyncClient) -> None:
    response = await spa_client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_no_mount_without_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRONTEND_DIST_DIR", str(tmp_path))
    get_settings.cache_clear()
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    get_settings.cache_clear()

    assert response.status_code == 404
