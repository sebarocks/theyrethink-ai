"""Tests del cargador de contexto (requieren Postgres, D11)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import DEFAULT_IDENTITY_PROMPT, AgentNotFoundError, load_agent_context
from app.models import Agent, AgentSource, KnowledgeSource, Role


async def test_custom_identity_takes_precedence(session: AsyncSession) -> None:
    session.add(Role(key="teacher", name="Profesor", prompt="Rol profesor [____]"))
    await session.flush()
    agent = Agent(name="ana", role_key="teacher", custom_identity="Identidad propia")
    session.add(agent)
    await session.flush()

    context = await load_agent_context(session, agent.id)
    assert context.identity_prompt == "Identidad propia"


async def test_role_prompt_is_used_and_markers_processed(session: AsyncSession) -> None:
    session.add(Role(key="teacher", name="Profesor", prompt="Eres [____], profesor."))
    await session.flush()
    agent = Agent(name="ana", profile="NOMBRE:\nAna Pérez", role_key="teacher")
    session.add(agent)
    await session.flush()

    context = await load_agent_context(session, agent.id)
    assert context.identity_prompt == "Eres Ana Pérez, profesor."


async def test_basic_role_is_the_fallback(session: AsyncSession) -> None:
    session.add(Role(key="basic", name="Básico", prompt="Rol básico"))
    agent = Agent(name="ana")
    session.add(agent)
    await session.flush()

    context = await load_agent_context(session, agent.id)
    assert context.identity_prompt == "Rol básico"


async def test_default_identity_when_no_roles(session: AsyncSession) -> None:
    agent = Agent(name="ana")
    session.add(agent)
    await session.flush()

    context = await load_agent_context(session, agent.id)
    assert context.identity_prompt == DEFAULT_IDENTITY_PROMPT


async def test_sources_are_ordered_by_id(session: AsyncSession) -> None:
    agent = Agent(name="ana")
    first = KnowledgeSource(name="Primera", content="uno")
    second = KnowledgeSource(name="Segunda", content="dos")
    session.add_all([agent, first, second])
    await session.flush()
    session.add_all(
        [
            AgentSource(agent_id=agent.id, source_id=second.id),
            AgentSource(agent_id=agent.id, source_id=first.id),
        ]
    )
    await session.flush()

    context = await load_agent_context(session, agent.id)
    assert [source.name for source in context.sources] == ["Primera", "Segunda"]


async def test_missing_agent_raises(session: AsyncSession) -> None:
    with pytest.raises(AgentNotFoundError):
        await load_agent_context(session, 999)
