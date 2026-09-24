"""Contrato de la vista admin de conversaciones (D18, ADR `0021`)."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.dto import MessageDTO
from app.api.deps import get_current_user
from app.api.v1.admin import get_agent_service
from app.db import get_session
from app.main import app
from app.models import Agent, Thread, User


class _FakeService:
    async def read_messages(self, *, thread_id: int) -> list[MessageDTO]:
        return [MessageDTO(role="user", text="hola"), MessageDTO(role="assistant", text="ey")]


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_agent_service] = lambda: _FakeService()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _as_user(session: AsyncSession, username: str, role: str = "usuario") -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash="hash",
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def _thread(session: AsyncSession, *, username: str, agent_name: str) -> tuple[User, Thread]:
    owner = await _as_user(session, username)
    agent = Agent(name=agent_name)
    session.add(agent)
    await session.flush()
    thread = Thread(agent_id=agent.id, user_id=owner.id, title="Charla", message_count=2)
    session.add(thread)
    await session.flush()
    return owner, thread


@pytest.mark.asyncio
async def test_regular_user_cannot_list_all_threads(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _as_user(session, "plain")
    app.dependency_overrides[get_current_user] = lambda: user

    response = await client.get("/api/v1/admin/threads")

    assert response.status_code == 403
    assert response.json()["code"] == "admin_required"


@pytest.mark.asyncio
async def test_admin_lists_threads_of_every_user(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _as_user(session, "auditor", role="admin")
    _, thread_a = await _thread(session, username="ana", agent_name="agente-a")
    await _thread(session, username="beto", agent_name="agente-b")
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.get("/api/v1/admin/threads")

    assert response.status_code == 200
    body = response.json()
    assert {row["username"] for row in body} == {"ana", "beto"}
    assert all({"agent_name", "message_count", "updated_at"} <= row.keys() for row in body)

    filtered = await client.get("/api/v1/admin/threads", params={"agent_id": thread_a.agent_id})
    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()] == [thread_a.id]


@pytest.mark.asyncio
async def test_admin_reads_any_transcript(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "reader", role="admin")
    _, thread = await _thread(session, username="caro", agent_name="agente-c")
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.get(f"/api/v1/admin/threads/{thread.id}/messages")

    assert response.status_code == 200
    assert response.json() == [
        {"role": "user", "text": "hola"},
        {"role": "assistant", "text": "ey"},
    ]


@pytest.mark.asyncio
async def test_missing_thread_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    admin = await _as_user(session, "reader-2", role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin

    response = await client.get("/api/v1/admin/threads/999999/messages")

    assert response.status_code == 404
    assert response.json()["code"] == "thread_not_found"
