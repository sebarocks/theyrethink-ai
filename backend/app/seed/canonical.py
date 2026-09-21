"""Carga de los datos canonicos portados desde `theythink-ai`.

El JSON (`data/canonical.json`) se genero una vez con `scripts/port_canonical_seed.py` a
partir del proyecto de referencia. Aqui solo se lee y se tipa; es la fuente de verdad del
seed y, por tanto, del artefacto *golden* de la Fase 5.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

__all__ = ["AgentSeed", "CanonicalSeed", "RoleSeed", "SourceSeed", "load_canonical"]

_DATA_FILE = Path(__file__).parent / "data" / "canonical.json"

ROLE_BASIC = "basic"


@dataclass(frozen=True)
class RoleSeed:
    key: str
    name: str
    description: str
    prompt: str
    is_system: bool


@dataclass(frozen=True)
class SourceSeed:
    name: str
    content: str


@dataclass(frozen=True)
class AgentSeed:
    name: str
    profile: str
    role_key: str | None
    custom_identity: str | None
    avatar_url: str | None
    source_names: tuple[str, ...]


@dataclass(frozen=True)
class CanonicalSeed:
    roles: tuple[RoleSeed, ...]
    sources: tuple[SourceSeed, ...]
    agents: tuple[AgentSeed, ...]


@lru_cache
def load_canonical() -> CanonicalSeed:
    """Devuelve el seed canonico, validado en la carga."""
    raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    seed = CanonicalSeed(
        roles=tuple(
            RoleSeed(
                key=r["key"],
                name=r["name"],
                description=r["description"],
                prompt=r["prompt"],
                is_system=bool(r["is_system"]),
            )
            for r in raw["roles"]
        ),
        sources=tuple(SourceSeed(name=s["name"], content=s["content"]) for s in raw["sources"]),
        agents=tuple(
            AgentSeed(
                name=a["name"],
                profile=a["profile"],
                role_key=a["role_key"],
                custom_identity=a["custom_identity"],
                avatar_url=a["avatar_url"],
                source_names=tuple(a["source_names"]),
            )
            for a in raw["agents"]
        ),
    )
    _validate(seed)
    return seed


def _validate(seed: CanonicalSeed) -> None:
    """Invariantes del seed: claves unicas y referencias existentes."""
    role_keys = {r.key for r in seed.roles}
    source_names = {s.name for s in seed.sources}

    if len(role_keys) != len(seed.roles):
        raise ValueError("roles.key duplicada en el seed canonico")
    if len(source_names) != len(seed.sources):
        raise ValueError("knowledge_sources.name duplicada en el seed canonico")
    if len({a.name for a in seed.agents}) != len(seed.agents):
        raise ValueError("agents.name duplicado en el seed canonico")
    if ROLE_BASIC not in role_keys:
        raise ValueError("falta el rol 'basic' en el seed canonico")

    for agent in seed.agents:
        if agent.role_key is not None and agent.role_key not in role_keys:
            raise ValueError(f"agente '{agent.name}' referencia un rol inexistente")
        missing = set(agent.source_names) - source_names
        if missing:
            raise ValueError(f"agente '{agent.name}' referencia fuentes inexistentes: {missing}")
