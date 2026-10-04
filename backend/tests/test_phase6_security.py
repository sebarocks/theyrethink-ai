"""Endurecimiento de la Fase 6: límite de peticiones, CSRF, cookie y contraseña.

D23 (ADR `0026`), D24 (ADR `0027`). Los tests del núcleo no usan red: `enforce_rate_limit` y
`password_policy_error` se prueban directamente; el resto pasa por la app con el `AsyncClient`.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SESSION_COOKIE, hash_session_token
from app.config import get_settings
from app.db import get_session
from app.main import app
from app.models import Session, User
from app.security import hash_password
from app.security.policy import password_policy_error
from app.security.rate_limit import RateLimitExceeded, enforce_rate_limit, window_start_for


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def _future() -> datetime:
    return datetime.now(UTC) + timedelta(days=1)


# --------------------------------------------------------------------------- contraseña


def test_password_policy_rejects_short_identity_and_accepts_valid() -> None:
    assert password_policy_error("corta", min_length=8) is not None
    assert password_policy_error("usuario123", username="usuario123") is not None
    assert password_policy_error("correo123", email="correo123@example.com") is not None
    assert password_policy_error("suficientemente-larga") is None


async def test_register_rejects_a_password_equal_to_the_username(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": "pepito123", "email": "p@example.com", "password": "pepito123"},
    )
    assert response.status_code == 422


async def test_login_cookie_carries_the_hardening_flags(
    client: AsyncClient, session: AsyncSession
) -> None:
    session.add(
        User(username="ana", email="ana@example.com", password_hash=hash_password("contrasena-1"))
    )
    await session.flush()

    response = await client.post(
        "/api/v1/auth/login", json={"username": "ana", "password": "contrasena-1"}
    )

    assert response.status_code == 200, response.text
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie


async def test_changing_the_password_revokes_the_other_sessions(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = User(
        username="ana", email="ana@example.com", password_hash=hash_password("contrasena-1")
    )
    session.add(user)
    await session.flush()
    token_here, token_elsewhere = "token-here", "token-elsewhere"
    session.add_all(
        [
            Session(
                user_id=user.id,
                token_hash=hash_session_token(token_here),
                expires_at=_future(),
            ),
            Session(
                user_id=user.id,
                token_hash=hash_session_token(token_elsewhere),
                expires_at=_future(),
            ),
        ]
    )
    await session.flush()
    client.cookies.set(SESSION_COOKIE, token_here)

    response = await client.patch(
        "/api/v1/auth/me",
        json={"current_password": "contrasena-1", "new_password": "contrasena-2"},
    )

    assert response.status_code == 200, response.text
    states = {
        row.token_hash: row.revoked_at
        for row in (await session.execute(select(Session).where(Session.user_id == user.id)))
        .scalars()
        .all()
    }
    assert states[hash_session_token(token_here)] is None
    assert states[hash_session_token(token_elsewhere)] is not None


# -------------------------------------------------------------------------------- CSRF


async def test_unsafe_request_with_a_foreign_origin_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "ana", "password": "x"},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "origin_not_allowed"


async def test_same_origin_request_passes_the_csrf_guard(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "no-existe", "password": "x"},
        headers={"Origin": "http://test"},
    )

    # Llega al handler: falla por credenciales, no por origen.
    assert response.status_code == 401


async def test_allowed_origins_extends_the_allowlist(client: AsyncClient) -> None:
    settings = get_settings()
    original = settings.allowed_origins
    settings.allowed_origins = ["https://app.example"]
    try:
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "no-existe", "password": "x"},
            headers={"Origin": "https://app.example"},
        )
    finally:
        settings.allowed_origins = original

    assert response.status_code == 401


# ---------------------------------------------------------------------- rate limiting


def test_window_start_is_aligned_to_the_window() -> None:
    moment = datetime(2026, 10, 2, 12, 0, 30, tzinfo=UTC)
    assert window_start_for(moment, 60) == window_start_for(moment, 60)
    assert window_start_for(moment, 60) % 60 == 0


async def test_fixed_window_counts_and_blocks_after_the_limit(session: AsyncSession) -> None:
    moment = datetime(2026, 10, 2, 12, 0, 0, tzinfo=UTC)
    for _ in range(3):
        await enforce_rate_limit(
            session, scope="test", key="k", limit=3, window_seconds=60, now=moment
        )

    with pytest.raises(RateLimitExceeded) as excinfo:
        await enforce_rate_limit(
            session, scope="test", key="k", limit=3, window_seconds=60, now=moment
        )

    assert excinfo.value.retry_after >= 1


async def test_login_is_rate_limited(client: AsyncClient) -> None:
    settings = get_settings()
    original = settings.rate_limit_auth_attempts
    settings.rate_limit_auth_attempts = 2
    try:
        payload = {"username": "no-existe", "password": "x"}
        assert (await client.post("/api/v1/auth/login", json=payload)).status_code == 401
        assert (await client.post("/api/v1/auth/login", json=payload)).status_code == 401

        blocked = await client.post("/api/v1/auth/login", json=payload)
    finally:
        settings.rate_limit_auth_attempts = original

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "too_many_requests"
    assert blocked.headers["retry-after"]
