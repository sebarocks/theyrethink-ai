"""Contrato del CRUD administrativo de agentes (PATCH/DELETE) y del perfil propio (D19)."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_session
from app.main import app
from app.models import Agent, KnowledgeSource, Role, User
from app.security import hash_password, verify_password


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _as_user(session: AsyncSession, username: str, role: str = "usuario") -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_password("secret123"),
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def _agent(session: AsyncSession, name: str) -> Agent:
    agent = Agent(name=name)
    session.add(agent)
    await session.flush()
    return agent


@pytest.mark.asyncio
async def test_regular_user_cannot_update_agent(client: AsyncClient, session: AsyncSession) -> None:
    user = await _as_user(session, "plain-agent")
    agent = await _agent(session, "objetivo")
    app.dependency_overrides[get_current_user] = lambda: user

    response = await client.patch(f"/api/v1/agents/{agent.id}", json={"name": "otro"})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_updates_agent(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "admin-agent", role="admin")
    session.add(Role(key="mentor", name="Mentor"))
    agent = await _agent(session, "editable")
    await session.flush()
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.patch(
        f"/api/v1/agents/{agent.id}",
        json={"name": "editado", "profile": "perfil", "role_key": "mentor"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "editado"
    assert response.json()["role_key"] == "mentor"


@pytest.mark.asyncio
async def test_agent_duplicate_name_returns_409(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "admin-dup", role="admin")
    await _agent(session, "tomado")
    agent = await _agent(session, "libre")
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.patch(f"/api/v1/agents/{agent.id}", json={"name": "tomado"})

    assert response.status_code == 409
    assert response.json()["code"] == "agent_name_taken"


@pytest.mark.asyncio
async def test_agent_unknown_role_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "admin-role", role="admin")
    agent = await _agent(session, "sin-rol")
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.patch(f"/api/v1/agents/{agent.id}", json={"role_key": "fantasma"})

    assert response.status_code == 404
    assert response.json()["code"] == "role_not_found"


@pytest.mark.asyncio
async def test_admin_deletes_agent(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "admin-del", role="admin")
    agent = await _agent(session, "a-borrar")
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.delete(f"/api/v1/agents/{agent.id}")

    assert response.status_code == 204
    assert await session.get(Agent, agent.id) is None


@pytest.mark.asyncio
async def test_missing_agent_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "admin-miss", role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.delete("/api/v1/agents/999999")

    assert response.status_code == 404
    assert response.json()["code"] == "agent_not_found"


@pytest.mark.asyncio
async def test_agent_sources_read_after_attach(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "admin-src", role="admin")
    agent = await _agent(session, "con-fuentes")
    source = KnowledgeSource(name="fuente-a", content="x")
    session.add(source)
    await session.flush()
    app.dependency_overrides[get_current_user] = lambda: admin

    attached = await client.put(f"/api/v1/agents/{agent.id}/sources/{source.id}")
    assert attached.status_code == 200

    response = await client.get(f"/api/v1/agents/{agent.id}/sources")

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [source.id]


@pytest.mark.asyncio
async def test_profile_update_changes_username_and_password(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _as_user(session, "perfil")
    app.dependency_overrides[get_current_user] = lambda: user

    response = await client.patch(
        "/api/v1/auth/me",
        json={
            "username": "perfil-nuevo",
            "current_password": "secret123",
            "new_password": "clave-nueva-123",
        },
    )

    assert response.status_code == 200
    assert response.json()["username"] == "perfil-nuevo"
    await session.refresh(user)
    assert verify_password(user.password_hash, "clave-nueva-123")


@pytest.mark.asyncio
async def test_profile_wrong_current_password_returns_400(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _as_user(session, "perfil-malo")
    app.dependency_overrides[get_current_user] = lambda: user

    response = await client.patch(
        "/api/v1/auth/me",
        json={"current_password": "incorrecta", "new_password": "clave-nueva-123"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_current_password"


@pytest.mark.asyncio
async def test_profile_duplicate_identity_returns_409(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _as_user(session, "perfil-dup")
    await _as_user(session, "ocupado")
    app.dependency_overrides[get_current_user] = lambda: user

    response = await client.patch("/api/v1/auth/me", json={"username": "ocupado"})

    assert response.status_code == 409
    assert response.json()["code"] == "identity_already_exists"
