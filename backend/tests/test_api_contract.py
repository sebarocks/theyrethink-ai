"""Pruebas HTTP de contrato y autorización de la API."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import main as main_module
from app.api.deps import get_current_user
from app.db import get_session
from app.main import app
from app.models import Agent, Role, Thread, User


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _as_user(session: AsyncSession, role: str = "usuario") -> User:
    user = User(
        username=f"user-{role}",
        email=f"{role}@example.com",
        password_hash="hash",
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_protected_endpoint_without_session_returns_stable_401(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/agents")

    assert response.status_code == 401
    assert response.json() == {
        "error": "authentication_error",
        "code": "authentication_required",
        "detail": "Se requiere una sesión válida.",
    }


@pytest.mark.asyncio
async def test_admin_mutation_rejects_regular_user(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _as_user(session)
    app.dependency_overrides[get_current_user] = lambda: user

    response = await client.post("/api/v1/roles", json={"key": "new", "name": "Nuevo"})

    assert response.status_code == 403
    assert response.json()["code"] == "admin_required"


@pytest.mark.asyncio
async def test_admin_mutation_returns_404_for_missing_role(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _as_user(session, role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.patch("/api/v1/roles/999999", json={"name": "No existe"})

    assert response.status_code == 404
    assert response.json()["code"] == "role_not_found"


@pytest.mark.asyncio
async def test_invalid_payload_returns_stable_422(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json={"username": "a"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert body["code"] == "invalid_request"
    assert isinstance(body["detail"], list)


@pytest.mark.asyncio
async def test_thread_belonging_hides_other_users_thread(
    client: AsyncClient, session: AsyncSession
) -> None:
    owner = await _as_user(session, role="usuario")
    other = await _as_user(session, role="admin")
    agent = Agent(name="contract-agent")
    session.add(agent)
    await session.flush()
    thread = Thread(agent_id=agent.id, user_id=owner.id)
    session.add(thread)
    await session.flush()
    app.dependency_overrides[get_current_user] = lambda: other

    response = await client.patch(f"/api/v1/threads/{thread.id}", json={"title": "Acceso indebido"})

    assert response.status_code == 404
    assert response.json()["code"] == "thread_not_found"


@pytest.mark.asyncio
async def test_duplicate_role_key_returns_409(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, role="admin")
    session.add(Role(key="duplicate", name="Original"))
    await session.flush()
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.post("/api/v1/roles", json={"key": "duplicate", "name": "Duplicado"})

    assert response.status_code == 409
    assert response.json()["code"] == "role_key_taken"


async def test_unknown_route_keeps_the_error_envelope(client: AsyncClient) -> None:
    """Los 404 del router (Starlette) también usan `{error, code, detail}`."""
    response = await client.get("/api/v1/ruta-que-no-existe")

    assert response.status_code == 404
    body = response.json()
    assert {"error", "code", "detail"} <= body.keys()


async def test_validation_error_does_not_echo_the_submitted_value(client: AsyncClient) -> None:
    """El 422 no refleja la contraseña recibida en `detail[].input`."""
    secret = "corta"
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": "abc", "email": "a@b.co", "password": secret},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_request"
    assert all("input" not in error for error in body["detail"])
    assert secret not in response.text


async def test_unhandled_error_returns_a_stable_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom() -> bool:
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(main_module, "ping_database", boom)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/readyz")

    assert response.status_code == 500
    assert response.json() == {
        "error": "internal_error",
        "code": "internal_error",
        "detail": "Error interno del servidor.",
    }
