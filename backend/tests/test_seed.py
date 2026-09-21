"""Tests del seed canonico: idempotencia, fidelidad al golden y sembrado del admin."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Agent, KnowledgeSource, Role, User
from app.security.passwords import verify_password
from app.seed import export_canonical_state, load_canonical, seed
from app.seed.export import golden_path


def test_canonical_seed_is_consistent() -> None:
    canonical = load_canonical()

    assert len(canonical.roles) == 23
    assert len(canonical.sources) == 19
    assert len(canonical.agents) == 19
    assert {a.name for a in canonical.agents} >= {"benjamin", "el_principito", "bodega_jefe"}


async def test_seed_twice_leaves_the_same_state(session: AsyncSession) -> None:
    await seed(session, include_admin=False)
    first = await export_canonical_state(session)

    await seed(session, include_admin=False)
    second = await export_canonical_state(session)

    assert first == second


async def test_seed_matches_golden_artifact(session: AsyncSession) -> None:
    await seed(session, include_admin=False)
    state = await export_canonical_state(session)

    golden = json.loads(golden_path().read_text(encoding="utf-8"))
    assert state == golden


async def test_seed_populates_expected_counts(session: AsyncSession) -> None:
    await seed(session, include_admin=False)

    async def count(model: type) -> int:
        return len((await session.execute(select(model))).scalars().all())

    assert await count(Role) == 23
    assert await count(KnowledgeSource) == 19
    assert await count(Agent) == 19


async def test_seed_links_agent_to_its_sources(session: AsyncSession) -> None:
    from app.models import AgentSource

    await seed(session, include_admin=False)
    agent = (await session.execute(select(Agent).where(Agent.name == "benjamin"))).scalar_one()
    source = (
        await session.execute(
            select(KnowledgeSource).where(KnowledgeSource.name == "Tecnología y Desarrollo Web")
        )
    ).scalar_one()

    link = (
        await session.execute(
            select(AgentSource).where(
                AgentSource.agent_id == agent.id, AgentSource.source_id == source.id
            )
        )
    ).scalar_one_or_none()
    assert link is not None


async def test_admin_is_seeded_only_with_password(session: AsyncSession, monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()
    await seed(session, include_admin=True)
    assert (
        await session.execute(select(User).where(User.username == "admin"))
    ).scalar_one_or_none() is None


async def test_admin_is_created_when_password_is_present(
    session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD", "a-strong-admin-password")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    get_settings.cache_clear()
    try:
        await seed(session, include_admin=True)
        admin = (await session.execute(select(User).where(User.username == "admin"))).scalar_one()
        assert admin.role == "admin"
        assert admin.email == "admin@example.com"
        assert verify_password(admin.password_hash, "a-strong-admin-password")
    finally:
        get_settings.cache_clear()
