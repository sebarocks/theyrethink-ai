"""Export del estado canonico a JSON versionado (artefacto *golden*, plan Fase 1).

Es el **oraculo de la Fase 5**: el migrador de `theythink-ai` debe reproducir exactamente
este estado (roles, agentes y fuentes), y la suite comprueba que sembrar dos veces produce
el mismo JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, AgentSource, KnowledgeSource, Role

__all__ = ["export_canonical_state", "golden_path", "write_golden"]

GOLDEN_FILE = Path(__file__).parent / "golden" / "canonical_state.json"


def golden_path() -> Path:
    return GOLDEN_FILE


async def export_canonical_state(session: AsyncSession) -> dict[str, Any]:
    """Estado canonico normalizado: ordenado y sin timestamps ni ids internos."""
    roles = (await session.execute(select(Role).order_by(Role.key))).scalars().all()
    sources = (
        (await session.execute(select(KnowledgeSource).order_by(KnowledgeSource.name)))
        .scalars()
        .all()
    )
    agents = (await session.execute(select(Agent).order_by(Agent.name))).scalars().all()

    link_rows = (
        await session.execute(
            select(AgentSource.agent_id, KnowledgeSource.name)
            .join(KnowledgeSource, KnowledgeSource.id == AgentSource.source_id)
            .order_by(AgentSource.agent_id, KnowledgeSource.name)
        )
    ).all()
    sources_by_agent: dict[int, list[str]] = {}
    for agent_id, source_name in link_rows:
        sources_by_agent.setdefault(agent_id, []).append(source_name)

    return {
        "roles": [
            {
                "key": role.key,
                "name": role.name,
                "description": role.description,
                "prompt": role.prompt,
                "is_system": role.is_system,
            }
            for role in roles
        ],
        "sources": [{"name": source.name, "content": source.content} for source in sources],
        "agents": [
            {
                "name": agent.name,
                "profile": agent.profile,
                "role_key": agent.role_key,
                "custom_identity": agent.custom_identity,
                "avatar_url": agent.avatar_url,
                "source_names": sources_by_agent.get(agent.id, []),
            }
            for agent in agents
        ],
    }


def write_golden(state: dict[str, Any], path: Path | None = None) -> Path:
    """Escribe el estado canonico como JSON versionado."""
    destination = path or GOLDEN_FILE
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination
