"""Seed canonico e idempotente.

Dos corridas consecutivas dejan **el mismo estado** (DoD de la Fase 1): las entidades se
hacen *upsert* por su clave natural (`roles.key`, `knowledge_sources.name`, `agents.name`) y
las asociaciones N:M se sincronizan exactamente con el seed, no de forma aditiva.

Requiere que el esquema de dominio exista (`alembic upgrade head`); no crea tablas.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Agent, AgentSource, KnowledgeSource, Role, User
from app.security.passwords import hash_password
from app.seed.canonical import AgentSeed, CanonicalSeed, load_canonical

__all__ = ["seed", "seed_admin"]

logger = logging.getLogger(__name__)


async def seed(session: AsyncSession, *, include_admin: bool = True) -> CanonicalSeed:
    """Siembra (o reconcilia) los datos canonicos. Idempotente."""
    canonical = load_canonical()

    for role_seed in canonical.roles:
        result = await session.execute(select(Role).where(Role.key == role_seed.key))
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(key=role_seed.key)
            session.add(role)
        role.name = role_seed.name
        role.description = role_seed.description
        role.prompt = role_seed.prompt
        role.is_system = role_seed.is_system

    for source_seed in canonical.sources:
        result = await session.execute(
            select(KnowledgeSource).where(KnowledgeSource.name == source_seed.name)
        )
        source = result.scalar_one_or_none()
        if source is None:
            source = KnowledgeSource(name=source_seed.name)
            session.add(source)
        source.content = source_seed.content

    await session.flush()

    rows = (await session.execute(select(KnowledgeSource.name, KnowledgeSource.id))).all()
    source_id_by_name = {name: id_ for name, id_ in rows}

    for agent_seed in canonical.agents:
        await _upsert_agent(session, agent_seed, source_id_by_name)

    await session.flush()

    if include_admin:
        await seed_admin(session)

    await session.commit()
    logger.info(
        "seed canonico completo (%d roles, %d fuentes, %d agentes)",
        len(canonical.roles),
        len(canonical.sources),
        len(canonical.agents),
    )
    return canonical


async def _upsert_agent(
    session: AsyncSession, agent_seed: AgentSeed, source_id_by_name: dict[str, int]
) -> None:
    result = await session.execute(select(Agent).where(Agent.name == agent_seed.name))
    agent = result.scalar_one_or_none()
    if agent is None:
        agent = Agent(name=agent_seed.name)
        session.add(agent)
    agent.profile = agent_seed.profile
    agent.role_key = agent_seed.role_key
    agent.custom_identity = agent_seed.custom_identity
    agent.avatar_url = agent_seed.avatar_url
    await session.flush()

    desired = {source_id_by_name[name] for name in agent_seed.source_names}
    rows = (
        await session.execute(select(AgentSource).where(AgentSource.agent_id == agent.id))
    ).scalars()
    existing = {row.source_id for row in rows}

    for source_id in existing - desired:
        await session.execute(
            delete(AgentSource).where(
                AgentSource.agent_id == agent.id, AgentSource.source_id == source_id
            )
        )
    for source_id in desired - existing:
        session.add(AgentSource(agent_id=agent.id, source_id=source_id))


async def seed_admin(session: AsyncSession) -> None:
    """Crea el primer `admin` si hay contrasena configurada (D13).

    No existe contrasena por defecto (AGENTS.md §5): si `ADMIN_PASSWORD` no esta definida,
    se omite y se avisa. No se reescribe la contrasena de un admin existente.
    """
    settings = get_settings()
    if not settings.admin_password:
        logger.warning(
            "ADMIN_PASSWORD no definida: no se siembra el usuario admin. "
            "Definela en el entorno para crear la primera cuenta."
        )
        return

    result = await session.execute(select(User).where(User.username == settings.admin_username))
    if result.scalar_one_or_none() is not None:
        return

    session.add(
        User(
            username=settings.admin_username,
            email=settings.admin_email or f"{settings.admin_username}@example.invalid",
            password_hash=hash_password(settings.admin_password),
            role="admin",
        )
    )
