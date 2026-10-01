"""Contrato del endpoint SSE de chat."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.dto import ChatChunk
from app.api.deps import get_agent_service, get_current_user
from app.api.v1.chat import HEARTBEAT_SECONDS, _event, router
from app.db import get_session
from app.main import app
from app.models import Agent, Thread, User


def test_chat_route_is_post_message_stream() -> None:
    routes = {(route.path, frozenset(route.methods or ())) for route in router.routes}
    assert ("/threads/{thread_id}/messages", frozenset({"POST"})) in routes
    assert HEARTBEAT_SECONDS > 0


def test_chat_route_includes_message_history() -> None:
    routes = {(route.path, frozenset(route.methods or ())) for route in router.routes}
    assert ("/threads/{thread_id}/messages", frozenset({"GET"})) in routes


def test_sse_event_format_is_stable() -> None:
    assert _event("heartbeat", {}) == "event: heartbeat\ndata: {}\n\n"
    assert _event("chunk", {"text": "hola"}) == ('event: chunk\ndata: {"text": "hola"}\n\n')


class FakeAgentService:
    """Servicio falso: registra lo que recibe y emite un chunk y el cierre."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, int, int, str]] = []
        self.turns: list[tuple[int, str, str]] = []

    async def send_message(
        self, *, agent_id: int, user_id: int, thread_id: int, text: str
    ) -> AsyncIterator[ChatChunk]:
        self.sent.append((agent_id, user_id, thread_id, text))
        yield ChatChunk(text="Hola")
        yield ChatChunk(done=True)

    async def record_turn(
        self, session: AsyncSession, *, thread_id: int, user_text: str, assistant_text: str
    ) -> None:
        self.turns.append((thread_id, user_text, assistant_text))


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def test_send_message_streams_and_records_the_turn(
    client: AsyncClient, session: AsyncSession
) -> None:
    """El `agent_id` se lee antes de cerrar la transacción: el servicio lo recibe correcto."""
    user = User(username="duenio-chat", email="duenio-chat@example.com", password_hash="h")
    agent = Agent(name="agente-chat")
    session.add_all([user, agent])
    await session.flush()
    thread = Thread(agent_id=agent.id, user_id=user.id)
    session.add(thread)
    await session.flush()
    user_id, agent_id, thread_id = user.id, agent.id, thread.id

    fake = FakeAgentService()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_agent_service] = lambda: fake

    response = await client.post(f"/api/v1/threads/{thread_id}/messages", json={"text": "hola"})

    assert response.status_code == 200, response.text
    assert "event: chunk" in response.text
    assert "event: done" in response.text
    assert fake.sent == [(agent_id, user_id, thread_id, "hola")]
    assert fake.turns == [(thread_id, "hola", "Hola")]
