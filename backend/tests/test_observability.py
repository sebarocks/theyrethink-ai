"""Observabilidad de la Fase 6: logs JSON, `request_id`, métricas y `/metrics` (D25, ADR `0028`)."""

import json
import logging
from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from sqlalchemy.ext.asyncio import AsyncSession

from app import metrics
from app.agent.dto import AgentContext
from app.agent.graph import _cached_tokens, build_chat_graph
from app.agent.memory import MemoryFact, memory_namespace, write_facts
from app.config import get_settings
from app.db import get_session
from app.logging_config import JsonFormatter, configure_logging, request_id_var
from app.main import app
from tests.fakes import RecordingFakeLLM

CONTEXT = AgentContext(
    agent_id=1,
    name="agente",
    profile="NOMBRE:\nAna",
    identity_prompt="Eres un profesor.",
    sources=(),
)


async def _load_context(agent_id: int) -> AgentContext:
    return CONTEXT


@pytest.fixture(autouse=True)
def _clean_metrics() -> Iterator[None]:
    metrics.reset()
    yield
    metrics.reset()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def test_json_formatter_serializes_event_fields_and_request_id() -> None:
    token = request_id_var.set("req-123")
    try:
        record = logging.LogRecord(
            name="app.agent",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="chat.respond",
            args=(),
            exc_info=None,
        )
        record.event = "chat.respond"
        record.thread_id = 7
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)

    assert payload["event"] == "chat.respond"
    assert payload["thread_id"] == 7
    assert payload["request_id"] == "req-123"
    assert payload["message"] == "chat.respond"


def test_configure_logging_applies_the_format_to_uvicorn_loggers() -> None:
    settings = get_settings()
    original = settings.log_format
    settings.log_format = "json"
    try:
        configure_logging(settings)
        formatter = logging.getLogger("uvicorn.access").handlers[0].formatter
    finally:
        settings.log_format = original
        configure_logging(settings)

    assert isinstance(formatter, JsonFormatter)


def test_metrics_render_uses_prometheus_shape() -> None:
    metrics.increment("memory_facts_injected_total", 2)

    text = metrics.render()

    assert "# TYPE memory_facts_injected_total counter" in text
    assert "memory_facts_injected_total 2" in text


def test_cached_tokens_reads_provider_usage_and_tolerates_absence() -> None:
    message = AIMessage(
        content="hola",
        usage_metadata={
            "input_tokens": 10,
            "output_tokens": 2,
            "total_tokens": 12,
            "input_token_details": {"cache_read": 8},
        },
    )

    assert _cached_tokens(message) == 8
    assert _cached_tokens(AIMessage(content="hola")) is None


async def test_request_id_is_echoed_and_generated(client: AsyncClient) -> None:
    echoed = await client.get("/healthz", headers={"X-Request-Id": "abc-123"})
    generated = await client.get("/healthz")

    assert echoed.headers["x-request-id"] == "abc-123"
    assert generated.headers["x-request-id"]


async def test_metrics_is_disabled_by_default(client: AsyncClient) -> None:
    response = await client.get("/metrics")

    assert response.status_code == 404


async def test_metrics_is_served_when_enabled(client: AsyncClient) -> None:
    settings = get_settings()
    original = settings.metrics_enabled
    settings.metrics_enabled = True
    try:
        metrics.increment("chat_turns_total", 3)
        response = await client.get("/metrics")
    finally:
        settings.metrics_enabled = original

    assert response.status_code == 200
    assert "chat_turns_total 3" in response.text


async def test_metrics_requires_the_token_when_configured(client: AsyncClient) -> None:
    settings = get_settings()
    original_enabled, original_token = settings.metrics_enabled, settings.metrics_token
    settings.metrics_enabled, settings.metrics_token = True, "s3cret"
    try:
        anonymous = await client.get("/metrics")
        authorized = await client.get("/metrics", headers={"Authorization": "Bearer s3cret"})
    finally:
        settings.metrics_enabled, settings.metrics_token = original_enabled, original_token

    assert anonymous.status_code == 401
    assert authorized.status_code == 200


async def test_chat_turn_records_injection_metrics() -> None:
    store = InMemoryStore()
    llm = RecordingFakeLLM(response="hola")
    graph = build_chat_graph(
        llm=llm,
        store=store,
        load_context=_load_context,
        context_tokens=1_000,
        count_tokens=lambda _text: 1,
        checkpointer=InMemorySaver(),
    )
    await write_facts(store, memory_namespace(1, 1), [MemoryFact(content="vive en Santiago")])

    await graph.ainvoke(
        {
            "agent_id": 1,
            "user_id": 1,
            "thread_id": "1",
            "messages": [HumanMessage(content="hola")],
        },
        config={"configurable": {"thread_id": "1"}},
    )

    text = metrics.render()
    assert "memory_injected_tokens_last 1" in text
    assert "memory_injection_budget_tokens 400" in text
    assert "chat_turns_total 1" in text
    assert "memory_facts_injected_total 1" in text
