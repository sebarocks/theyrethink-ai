"""Contrato de autorización y CRUD administrativo de usuarios (D17, ADR `0021`)."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_session
from app.main import app
from app.models import User
from app.security import hash_password


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


@pytest.mark.asyncio
async def test_regular_user_cannot_list_users(client: AsyncClient, session: AsyncSession) -> None:
    user = await _as_user(session, "plain-user")
    app.dependency_overrides[get_current_user] = lambda: user

    response = await client.get("/api/v1/users")

    assert response.status_code == 403
    assert response.json()["code"] == "admin_required"


@pytest.mark.asyncio
async def test_admin_creates_and_lists_users(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "root-admin", role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin

    created = await client.post(
        "/api/v1/users",
        json={
            "username": "nuevo",
            "email": "nuevo@example.com",
            "password": "secret123",
            "role": "admin",
        },
    )
    assert created.status_code == 201
    assert created.json()["role"] == "admin"
    assert "password" not in created.json()

    listed = await client.get("/api/v1/users")
    assert listed.status_code == 200
    assert {user["username"] for user in listed.json()} >= {"root-admin", "nuevo"}


@pytest.mark.asyncio
async def test_duplicate_identity_returns_409(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "dup-admin", role="admin")
    await _as_user(session, "ocupado")
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.post(
        "/api/v1/users",
        json={"username": "ocupado", "email": "otro@example.com", "password": "secret123"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "identity_already_exists"


@pytest.mark.asyncio
async def test_admin_updates_role_and_password(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "edit-admin", role="admin")
    target = await _as_user(session, "edit-target")
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.patch(
        f"/api/v1/users/{target.id}",
        json={"role": "admin", "password": "nueva-clave-123"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    await session.refresh(target)
    assert target.password_hash != "hash"


@pytest.mark.asyncio
async def test_admin_cannot_demote_self(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "self-admin", role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.patch(f"/api/v1/users/{admin.id}", json={"role": "usuario"})

    assert response.status_code == 409
    assert response.json()["code"] == "cannot_modify_self"


@pytest.mark.asyncio
async def test_admin_cannot_delete_self(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "del-admin", role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.delete(f"/api/v1/users/{admin.id}")

    assert response.status_code == 409
    assert response.json()["code"] == "cannot_modify_self"


@pytest.mark.asyncio
async def test_admin_deletes_another_user(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "root-del", role="admin")
    target = await _as_user(session, "borrame")
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.delete(f"/api/v1/users/{target.id}")

    assert response.status_code == 204
    assert await session.get(User, target.id) is None


@pytest.mark.asyncio
async def test_missing_user_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "missing-admin", role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.patch("/api/v1/users/999999", json={"username": "nadie"})

    assert response.status_code == 404
    assert response.json()["code"] == "user_not_found"
