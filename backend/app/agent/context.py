"""Resolucion del contexto de un agente desde la base de datos.

Vive dentro de `app/agent/` porque es parte de la costura, pero es **I/O de dominio**: lee
`agents`, `roles` y `knowledge_sources` y devuelve un `AgentContext` (DTO). El grafo lo
consume sin tocar la base, y en los tests se sustituye por un cargador falso (AGENTS.md §6).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.dto import AgentContext
from app.agent.prompts import (
    SourceText,
    process_identity,
    resolve_identity_prompt,
    resolve_person_name,
)
from app.models import Agent, AgentSource, KnowledgeSource, Role

__all__ = ["AgentNotFoundError", "DEFAULT_IDENTITY_PROMPT", "load_agent_context"]

# Ultimo recurso si el agente no tiene identidad propia ni rol (paridad con `info_identidad`).
DEFAULT_IDENTITY_PROMPT = "Eres un asistente útil."


class AgentNotFoundError(LookupError):
    """El `agent_id` no existe."""


async def _role_prompt(session: AsyncSession, role_key: str | None) -> str | None:
    """Prompt del rol indicado, o del rol `basic` como respaldo."""
    if role_key:
        role = (
            await session.execute(select(Role).where(Role.key == role_key))
        ).scalar_one_or_none()
        if role is not None and role.prompt.strip():
            return role.prompt
    basic = (await session.execute(select(Role).where(Role.key == "basic"))).scalar_one_or_none()
    return basic.prompt if basic is not None else None


async def _sources(session: AsyncSession, agent_id: int) -> tuple[SourceText, ...]:
    """Fuentes asociadas al agente, en orden determinista (por `id`) para el prompt estable."""
    rows = (
        await session.execute(
            select(KnowledgeSource)
            .join(AgentSource, AgentSource.source_id == KnowledgeSource.id)
            .where(AgentSource.agent_id == agent_id)
            .order_by(KnowledgeSource.id)
        )
    ).scalars()
    return tuple(SourceText(name=source.name, content=source.content) for source in rows)


async def load_agent_context(session: AsyncSession, agent_id: int) -> AgentContext:
    """Resuelve identidad, perfil y fuentes de un agente.

    Precedencia de identidad (paridad con `info_identidad`): identidad personalizada > rol >
    rol `basic` > prompt por defecto. Los marcadores del prompt se procesan aqui con el nombre
    de la persona, de modo que el grafo recibe la identidad lista para usar.
    """
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise AgentNotFoundError(f"agente {agent_id} inexistente")

    raw_identity = resolve_identity_prompt(
        custom_identity=agent.custom_identity,
        role_prompt=await _role_prompt(session, agent.role_key),
        default_prompt=DEFAULT_IDENTITY_PROMPT,
    )
    person_name = resolve_person_name(agent.name, agent.profile)

    return AgentContext(
        agent_id=agent_id,
        name=agent.name,
        profile=agent.profile,
        identity_prompt=process_identity(raw_identity, person_name),
        sources=await _sources(session, agent_id),
    )
