"""Contrato de la memoria visible y olvidable (D10)."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory import MemoryFact
from app.api.deps import get_agent_service, get_current_user
from app.db import get_session
from app.main import app
from app.models import Agent, User


class FakeMemoryService:
    """Servicio falso con memoria por `(agente, usuario)` (el Store se prueba en el núcleo)."""

    def __init__(self) -> None:
        self.facts: dict[tuple[int, int], list[MemoryFact]] = {}

    async def read_memory(self, *, agent_id: int, user_id: int) -> list[MemoryFact]:
        return list(self.facts.get((agent_id, user_id), []))

    async def forget_memory(self, *, agent_id: int, user_id: int) -> int:
        return len(self.facts.pop((agent_id, user_id), []))


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _user(session: AsyncSession, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash="hash",
        role="usuario",
    )
    session.add(user)
    await session.flush()
    return user


async def _agent(session: AsyncSession, name: str = "agente-memoria") -> Agent:
    agent = Agent(name=name)
    session.add(agent)
    await session.flush()
    return agent


async def test_read_memory_returns_only_the_current_users_facts(
    client: AsyncClient, session: AsyncSession
) -> None:
    owner = await _user(session, "duenio-memoria")
    other = await _user(session, "otro-memoria")
    agent = await _agent(session)
    fake = FakeMemoryService()
    fake.facts[(agent.id, owner.id)] = [MemoryFact(content="vive en Santiago")]
    fake.facts[(agent.id, other.id)] = [MemoryFact(content="secreto de otro")]
    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_agent_service] = lambda: fake

    response = await client.get(f"/api/v1/agents/{agent.id}/memory")

    assert response.status_code == 200, response.text
    assert response.json() == {"facts": [{"content": "vive en Santiago", "category": None}]}


async def test_forget_memory_clears_only_the_current_user(
    client: AsyncClient, session: AsyncSession
) -> None:
    owner = await _user(session, "duenio-olvido")
    other = await _user(session, "otro-olvido")
    agent = await _agent(session, "agente-olvido")
    fake = FakeMemoryService()
    fake.facts[(agent.id, owner.id)] = [MemoryFact(content="a"), MemoryFact(content="b")]
    fake.facts[(agent.id, other.id)] = [MemoryFact(content="c")]
    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_agent_service] = lambda: fake

    response = await client.delete(f"/api/v1/agents/{agent.id}/memory")

    assert response.status_code == 204
    assert await fake.read_memory(agent_id=agent.id, user_id=owner.id) == []
    assert len(await fake.read_memory(agent_id=agent.id, user_id=other.id)) == 1
    # Tras olvidar, la lectura devuelve vacío.
    follow_up = await client.get(f"/api/v1/agents/{agent.id}/memory")
    assert follow_up.json() == {"facts": []}


async def test_memory_of_unknown_agent_returns_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _user(session, "usuario-404-memoria")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_agent_service] = lambda: FakeMemoryService()

    read = await client.get("/api/v1/agents/999999/memory")
    forget = await client.delete("/api/v1/agents/999999/memory")

    assert read.status_code == 404
    assert read.json()["code"] == "agent_not_found"
    assert forget.status_code == 404
