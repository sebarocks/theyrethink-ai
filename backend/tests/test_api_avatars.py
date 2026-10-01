"""Contrato, validadores y subida de avatares (D12, AGENTS.md §5)."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1 import agents as agents_module
from app.api.v1.agents import _AVATAR_TYPES, MAX_AVATAR_BYTES, _matches_signature, router
from app.db import get_session
from app.main import app
from app.models import Agent, User

# Muestras mínimas con la cabecera real de cada formato.
REAL_SAMPLES = {
    "image/jpeg": bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"jpeg",
    "image/png": bytes([0x89]) + b"PNG\r\n\x1a\n" + b"png",
    "image/gif": b"GIF89a" + b"gif",
    "image/webp": b"RIFF\x00\x00\x00\x00WEBPVP8 ",
}


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def test_avatar_routes_are_explicit() -> None:
    routes = {(route.path, frozenset(route.methods or ())) for route in router.routes}
    assert ("/agents/{agent_id}/avatar", frozenset({"POST"})) in routes
    assert ("/agents/{agent_id}/avatar", frozenset({"GET"})) in routes
    assert ("/agents/{agent_id}/avatar", frozenset({"DELETE"})) in routes


def test_avatars_allow_only_non_svg_raster_signatures() -> None:
    assert MAX_AVATAR_BYTES == 5 * 1024 * 1024
    assert set(_AVATAR_TYPES) == {"image/jpeg", "image/png", "image/gif", "image/webp"}
    assert not any(extension == ".svg" for _, extension in _AVATAR_TYPES.values())


@pytest.mark.parametrize("content_type", sorted(REAL_SAMPLES))
def test_real_raster_signatures_are_accepted(content_type: str) -> None:
    """Un archivo real de cada formato debe pasar la validación de firma."""
    assert _matches_signature(content_type, REAL_SAMPLES[content_type])


def test_content_must_match_declared_type() -> None:
    """Un SVG o HTML no puede colarse declarándose imagen."""
    svg = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
    html = b"<html><script>alert(1)</script></html>"
    for content_type in REAL_SAMPLES:
        assert not _matches_signature(content_type, svg)
        assert not _matches_signature(content_type, html)
    # La representación escapada del JPEG no es la firma real: no debe pasar.
    assert not _matches_signature("image/jpeg", b"\\xff\\xd8\\xff" + html)


def test_webp_requires_the_webp_marker_not_just_riff() -> None:
    """«RIFF» abre también WAV/AVI: hay que exigir el marcador WEBP del offset 8."""
    assert not _matches_signature("image/webp", b"RIFF\x00\x00\x00\x00WAVEfmt ")
    assert _matches_signature("image/webp", b"RIFF\x00\x00\x00\x00WEBPVP8 ")


async def _admin(session: AsyncSession) -> User:
    user = User(
        username="admin-avatar",
        email="admin-avatar@example.com",
        password_hash="hash",
        role="admin",
    )
    session.add(user)
    await session.flush()
    return user


def _stored_files(directory: Path) -> list[Path]:
    """Listado sincrónico: separa el I/O de archivo del cuerpo async del test."""
    return list(directory.iterdir())


async def test_admin_uploads_a_real_jpeg(
    client: AsyncClient,
    session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La subida end-to-end acepta un raster real y guarda el archivo fuera del estático."""
    monkeypatch.setattr(agents_module, "_avatar_directory", lambda: tmp_path)
    admin = await _admin(session)
    agent = Agent(name="avatar-agent")
    session.add(agent)
    await session.flush()
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.post(
        f"/api/v1/agents/{agent.id}/avatar",
        files={"file": ("foto.jpg", REAL_SAMPLES["image/jpeg"], "image/jpeg")},
    )

    assert response.status_code == 200, response.text
    assert str(response.json()["avatar_url"]).endswith(".jpg")
    stored = _stored_files(tmp_path)
    assert len(stored) == 1
    assert stored[0].suffix == ".jpg"


async def test_admin_cannot_upload_svg_disguised_as_image(
    client: AsyncClient,
    session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(agents_module, "_avatar_directory", lambda: tmp_path)
    admin = await _admin(session)
    agent = Agent(name="avatar-agent-2")
    session.add(agent)
    await session.flush()
    app.dependency_overrides[get_current_user] = lambda: admin

    disguised = await client.post(
        f"/api/v1/agents/{agent.id}/avatar",
        files={"file": ("evil.jpg", b"<svg onload=alert(1)/>", "image/jpeg")},
    )
    declared = await client.post(
        f"/api/v1/agents/{agent.id}/avatar",
        files={"file": ("evil.svg", b"<svg/>", "image/svg+xml")},
    )

    assert disguised.status_code == 400
    assert disguised.json()["code"] == "invalid_content"
    assert declared.status_code == 400
    assert declared.json()["code"] == "unsupported_type"
    assert _stored_files(tmp_path) == []
