"""Tests de los modelos de dominio y sus restricciones (requieren Postgres, D11)."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, KnowledgeSource, Role, Thread, User


def _user(username: str = "alice", email: str = "alice@example.com") -> User:
    return User(username=username, email=email, password_hash="hash")


async def test_user_defaults_to_usuario_role(session: AsyncSession) -> None:
    user = _user()
    session.add(user)
    await session.flush()

    assert user.id is not None
    assert user.role == "usuario"
    assert user.created_at is not None


async def test_username_and_email_are_unique(session: AsyncSession) -> None:
    session.add(_user("bob", "bob@example.com"))
    await session.flush()

    session.add(_user("bob", "other@example.com"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_role_is_constrained(session: AsyncSession) -> None:
    session.add(User(username="carol", email="carol@example.com", password_hash="h", role="root"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_agent_role_key_references_roles_and_nulls_on_delete(session: AsyncSession) -> None:
    role = Role(key="teacher", name="Profesor")
    session.add(role)
    await session.flush()

    agent = Agent(name="benjamin", role_key="teacher")
    session.add(agent)
    await session.flush()
    assert agent.role_key == "teacher"

    await session.delete(role)
    await session.flush()
    await session.refresh(agent)
    assert agent.role_key is None


async def test_agent_role_key_requires_existing_role(session: AsyncSession) -> None:
    session.add(Agent(name="ghost", role_key="missing_role"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_agent_sources_is_n_to_m(session: AsyncSession) -> None:
    from app.models import AgentSource

    source = KnowledgeSource(name="Doc")
    agent_a = Agent(name="a")
    agent_b = Agent(name="b")
    session.add_all([source, agent_a, agent_b])
    await session.flush()

    session.add_all(
        [
            AgentSource(agent_id=agent_a.id, source_id=source.id),
            AgentSource(agent_id=agent_b.id, source_id=source.id),
        ]
    )
    await session.flush()

    session.add(AgentSource(agent_id=agent_a.id, source_id=source.id))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_thread_holds_only_metadata(session: AsyncSession) -> None:
    user = _user()
    agent = Agent(name="assistant")
    session.add_all([user, agent])
    await session.flush()

    thread = Thread(agent_id=agent.id, user_id=user.id)
    session.add(thread)
    await session.flush()

    assert thread.message_count == 0
    assert thread.last_preview == ""
    assert thread.last_consolidated_at is None


async def test_deleting_user_cascades_threads(session: AsyncSession) -> None:
    from sqlalchemy import func, select

    user = _user()
    agent = Agent(name="assistant")
    session.add_all([user, agent])
    await session.flush()
    session.add(Thread(agent_id=agent.id, user_id=user.id))
    await session.flush()

    await session.delete(user)
    await session.flush()

    count = (await session.execute(select(func.count()).select_from(Thread))).scalar_one()
    assert count == 0
