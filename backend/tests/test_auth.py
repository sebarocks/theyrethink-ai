"""Pruebas unitarias y de contrato del bloque de autenticación."""

import hashlib
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SESSION_COOKIE, hash_session_token
from app.api.v1.auth import router
from app.db import get_session
from app.main import app
from app.models import User
from app.security import hash_password, verify_password


def test_passwords_use_argon2_and_verify() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2")
    assert verify_password(hashed, "correct horse battery staple")
    assert not verify_password(hashed, "wrong")


def test_session_token_is_stored_as_fixed_length_digest() -> None:
    digest = hash_session_token("opaque-token")
    assert len(digest) == 64
    assert digest != "opaque-token"


def test_auth_contract_exposes_public_and_protected_operations() -> None:
    routes = {(route.path, tuple(route.methods)) for route in router.routes}
    assert ("/auth/register", ("POST",)) in routes
    assert ("/auth/login", ("POST",)) in routes
    assert ("/auth/logout", ("POST",)) in routes
    assert ("/auth/me", ("GET",)) in routes
    assert SESSION_COOKIE == "theyrethink_session"


def _werkzeug_scrypt(password: str) -> str:
    salt = "0123456789abcdef"
    n, r, p = 2**15, 8, 1
    derived = hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=n, r=r, p=p, maxmem=132 * n * r * p
    ).hex()
    return f"scrypt:{n}:{r}:{p}${salt}${derived}"


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def test_login_rehashes_a_migrated_werkzeug_hash(
    client: AsyncClient, session: AsyncSession
) -> None:
    """El hash heredado se verifica y se reescribe a Argon2 en el primer login (Fase 5)."""
    user = User(
        username="migrado",
        email="migrado@example.com",
        password_hash=_werkzeug_scrypt("secreta123"),
    )
    session.add(user)
    await session.flush()

    response = await client.post(
        "/api/v1/auth/login", json={"username": "migrado", "password": "secreta123"}
    )

    assert response.status_code == 200, response.text
    assert user.password_hash.startswith("$argon2")
    # Una vez re-hasheado, la contraseña incorrecta sigue fallando.
    wrong = await client.post(
        "/api/v1/auth/login", json={"username": "migrado", "password": "otra"}
    )
    assert wrong.status_code == 401
