"""Matriz de autorización por endpoint: 401 sin sesión, 403 sin privilegios, 404 ajeno.

AGENTS.md §5 exige que ningún endpoint mutador quede sin política y §6 un test paramétrico
401/403/404 por endpoint. Este módulo cubre la matriz completa; los casos concretos de cada
router viven en su propio archivo.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_session
from app.main import app
from app.models import Agent, Thread, User

# Rutas que exigen sesión válida. El cuerpo tiene que ser válido para que la petición llegue
# a la dependencia de autenticación (FastAPI valida el body antes de resolver dependencias).
PROTECTED_ROUTES = [
    pytest.param("GET", "/api/v1/agents", None, id="agents-list"),
    pytest.param("POST", "/api/v1/agents", {"name": "x"}, id="agents-create"),
    pytest.param("PATCH", "/api/v1/agents/1", {"name": "x"}, id="agents-update"),
    pytest.param("DELETE", "/api/v1/agents/1", None, id="agents-delete"),
    pytest.param("GET", "/api/v1/roles", None, id="roles-list"),
    pytest.param("POST", "/api/v1/roles", {"key": "k", "name": "N"}, id="roles-create"),
    pytest.param("PATCH", "/api/v1/roles/1", {"name": "N"}, id="roles-update"),
    pytest.param("DELETE", "/api/v1/roles/1", None, id="roles-delete"),
    pytest.param("GET", "/api/v1/sources", None, id="sources-list"),
    pytest.param("POST", "/api/v1/sources", {"name": "x"}, id="sources-create"),
    pytest.param("PATCH", "/api/v1/sources/1", {"name": "x"}, id="sources-update"),
    pytest.param("DELETE", "/api/v1/sources/1", None, id="sources-delete"),
    pytest.param("GET", "/api/v1/threads", None, id="threads-list"),
    pytest.param("POST", "/api/v1/threads", {"agent_id": 1}, id="threads-create"),
    pytest.param("PATCH", "/api/v1/threads/1", {"title": "x"}, id="threads-update"),
    pytest.param("DELETE", "/api/v1/threads/1", None, id="threads-delete"),
    pytest.param("GET", "/api/v1/threads/1/messages", None, id="chat-history"),
    pytest.param("POST", "/api/v1/threads/1/messages", {"text": "hola"}, id="chat-send"),
    pytest.param("GET", "/api/v1/users", None, id="users-list"),
    pytest.param(
        "POST",
        "/api/v1/users",
        {"username": "abc", "email": "a@b.co", "password": "password1"},
        id="users-create",
    ),
    pytest.param("PATCH", "/api/v1/users/1", {"role": "usuario"}, id="users-update"),
    pytest.param("DELETE", "/api/v1/users/1", None, id="users-delete"),
    pytest.param("GET", "/api/v1/admin/threads", None, id="admin-threads"),
    pytest.param("GET", "/api/v1/admin/threads/1/messages", None, id="admin-messages"),
    pytest.param("GET", "/api/v1/auth/me", None, id="auth-me"),
    pytest.param("POST", "/api/v1/auth/logout", None, id="auth-logout"),
]

# Rutas que exigen además rol administrador.
ADMIN_ROUTES = [
    pytest.param("POST", "/api/v1/agents", {"name": "x"}, id="agents-create"),
    pytest.param("PATCH", "/api/v1/agents/1", {"name": "x"}, id="agents-update"),
    pytest.param("DELETE", "/api/v1/agents/1", None, id="agents-delete"),
    pytest.param("POST", "/api/v1/roles", {"key": "k", "name": "N"}, id="roles-create"),
    pytest.param("PATCH", "/api/v1/roles/1", {"name": "N"}, id="roles-update"),
    pytest.param("DELETE", "/api/v1/roles/1", None, id="roles-delete"),
    pytest.param("POST", "/api/v1/sources", {"name": "x"}, id="sources-create"),
    pytest.param("PATCH", "/api/v1/sources/1", {"name": "x"}, id="sources-update"),
    pytest.param("DELETE", "/api/v1/sources/1", None, id="sources-delete"),
    pytest.param("GET", "/api/v1/users", None, id="users-list"),
    pytest.param(
        "POST",
        "/api/v1/users",
        {"username": "abc", "email": "a@b.co", "password": "password1"},
        id="users-create",
    ),
    pytest.param("PATCH", "/api/v1/users/1", {"role": "usuario"}, id="users-update"),
    pytest.param("DELETE", "/api/v1/users/1", None, id="users-delete"),
    pytest.param("GET", "/api/v1/admin/threads", None, id="admin-threads"),
    pytest.param("GET", "/api/v1/admin/threads/1/messages", None, id="admin-messages"),
]


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    # Los endpoints de hilos resuelven `app.state.agent_service` como dependencia, y el
    # `lifespan` no corre bajo ASGITransport. En estos tests la petición siempre se corta
    # antes (autorización o pertenencia), así que basta un centinela.
    app.state.agent_service = object()
    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        del app.state.agent_service


async def _user(session: AsyncSession, username: str, role: str = "usuario") -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash="hash",
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.parametrize("method,path,payload", PROTECTED_ROUTES)
async def test_protected_route_requires_session(
    client: AsyncClient, method: str, path: str, payload: object
) -> None:
    response = await client.request(method, path, json=payload)
    assert response.status_code == 401, f"{method} {path} -> {response.text}"
    assert response.json()["code"] in {"authentication_required", "invalid_session"}


@pytest.mark.parametrize("method,path,payload", ADMIN_ROUTES)
async def test_admin_route_rejects_regular_user(
    client: AsyncClient,
    session: AsyncSession,
    method: str,
    path: str,
    payload: object,
) -> None:
    user = await _user(session, "usuario-sin-privilegios")
    app.dependency_overrides[get_current_user] = lambda: user

    response = await client.request(method, path, json=payload)
    assert response.status_code == 403, f"{method} {path} -> {response.text}"
    assert response.json()["code"] == "admin_required"


async def test_thread_routes_hide_another_users_thread(
    client: AsyncClient, session: AsyncSession
) -> None:
    owner = await _user(session, "duenio")
    intruder = await _user(session, "intruso")
    agent = Agent(name="authz-agent")
    session.add(agent)
    await session.flush()
    thread = Thread(agent_id=agent.id, user_id=owner.id)
    session.add(thread)
    await session.flush()
    app.dependency_overrides[get_current_user] = lambda: intruder

    path = f"/api/v1/threads/{thread.id}"
    cases = [
        ("PATCH", path, {"title": "x"}),
        ("DELETE", path, None),
        ("GET", f"{path}/messages", None),
        ("POST", f"{path}/messages", {"text": "hola"}),
    ]
    for method, target, payload in cases:
        response = await client.request(method, target, json=payload)
        assert response.status_code == 404, f"{method} {target} -> {response.text}"
        assert response.json()["code"] == "thread_not_found"


async def test_avatar_write_requires_session_and_admin(
    client: AsyncClient, session: AsyncSession
) -> None:
    jpeg = {"file": ("a.jpg", bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"jpeg", "image/jpeg")}
    response = await client.post("/api/v1/agents/1/avatar", files=jpeg)
    assert response.status_code == 401

    user = await _user(session, "usuario-avatar")
    app.dependency_overrides[get_current_user] = lambda: user
    response = await client.post(
        "/api/v1/agents/1/avatar",
        files={"file": ("a.jpg", bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"jpeg", "image/jpeg")},
    )
    assert response.status_code == 403
    response = await client.delete("/api/v1/agents/1/avatar")
    assert response.status_code == 403


async def test_create_thread_with_unknown_agent_returns_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _user(session, "usuario-hilo")
    app.dependency_overrides[get_current_user] = lambda: user

    response = await client.post("/api/v1/threads", json={"agent_id": 999_999})

    assert response.status_code == 404
    assert response.json()["code"] == "agent_not_found"
