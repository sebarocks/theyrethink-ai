"""DTOs de dominio del nucleo del agente.

`agent/service.py` es la API publica del nucleo y devuelve **estos** tipos, nunca
`BaseMessage` ni tipos de LangGraph/LangChain (AGENTS.md §3.2, ADR `0006`). Los routers de
FastAPI no conocen la libreria: solo ven estos objetos.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Literal

from app.agent.prompts import SourceText

__all__ = [
    "AgentContext",
    "ChatChunk",
    "ConsolidationJobDTO",
    "MessageDTO",
    "ThreadMetadata",
]


@dataclass(frozen=True)
class AgentContext:
    """Configuracion resuelta de un agente, lista para construir su system prompt.

    La resuelve la capa de datos (`agent/context.py`) a partir de `agents`, `roles` y
    `knowledge_sources`; el grafo la consume sin tocar la base.
    """

    agent_id: int
    name: str
    profile: str
    identity_prompt: str
    sources: tuple[SourceText, ...] = ()


@dataclass(frozen=True)
class ChatChunk:
    """Fragmento de la respuesta en streaming.

    `text` es el delta de tokens; `done=True` marca el cierre del stream. El texto completo
    se reconstruye concatenando los deltas, de modo que el llamador no necesita el
    `BaseMessage` de la libreria.
    """

    text: str = ""
    done: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MessageDTO:
    """Mensaje del transcript de un hilo (solo `user`/`assistant`).

    El `system_prompt` y la memoria inyectada **no** forman parte del transcript: no son
    conversacion (D7, D16).
    """

    role: Literal["user", "assistant"]
    text: str


@dataclass(frozen=True)
class ThreadMetadata:
    """Metadatos de hilo para el dashboard. **Cache de UI, no fuente de verdad** (§3.4)."""

    id: int
    agent_id: int
    user_id: int
    title: str
    message_count: int
    last_preview: str
    created_at: dt.datetime
    updated_at: dt.datetime
    last_consolidated_at: dt.datetime | None = None


@dataclass(frozen=True)
class ConsolidationJobDTO:
    """Trabajo de consolidacion reclamado de la cola.

    `created_at` es la marca de agua: si el hilo ya consolido hasta ese instante, el trabajo
    se descarta (idempotencia ante reintentos, D7).
    """

    id: int
    thread_id: int
    agent_id: int
    user_id: int
    created_at: dt.datetime
    attempts: int = 0
