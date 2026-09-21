"""Modelos de dominio (SQLModel) mapeados al esquema de la propuesta §6.1.

Este modulo es la unica autoridad sobre el esquema **nuestro**. Las tablas de LangGraph
(checkpointer y `Store`) no se modelan aqui: las gestiona la libreria con `setup()` en el
arranque (ver `docs/spikes/S2-*` y el orden de arranque documentado en `alembic/README`).

Convenciones:
- Nombres de tabla y columna en ingles (AGENTS.md §7).
- Timestamps en UTC (`TIMESTAMP WITH TIME ZONE`, `server_default=now()`).
- Toda relacion declara su `ON DELETE`.
- No hay columnas de mensajes, sesiones ni memoria: eso vive en el checkpointer/`Store`.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlmodel import Field, SQLModel

__all__ = [
    "Agent",
    "AgentSource",
    "KnowledgeSource",
    "Role",
    "Thread",
    "User",
]


class User(SQLModel, table=True):
    """Cuenta de usuario (D6/D13). No hay usuarios anonimos ni identidades por canal."""

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'usuario')", name="ck_users_role"),)

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column(String(64), nullable=False, unique=True, index=True))
    email: str = Field(sa_column=Column(String(255), nullable=False, unique=True, index=True))
    password_hash: str = Field(sa_column=Column(String(255), nullable=False))
    role: str = Field(
        default="usuario",
        sa_column=Column(String(16), nullable=False, server_default="usuario"),
    )
    created_at: dt.datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
        )
    )


class Role(SQLModel, table=True):
    """Rol/identidad de sistema con su prompt (portado de `identidades.py`)."""

    __tablename__ = "roles"

    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(sa_column=Column(String(64), nullable=False, unique=True, index=True))
    name: str = Field(sa_column=Column(String(128), nullable=False))
    description: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    prompt: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    is_system: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    created_at: dt.datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )
    updated_at: dt.datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )
    )


class KnowledgeSource(SQLModel, table=True):
    """Fuente de conocimiento, compartible por varios agentes (N:M)."""

    __tablename__ = "knowledge_sources"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(200), nullable=False, unique=True, index=True))
    content: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    created_at: dt.datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )


class Agent(SQLModel, table=True):
    """Agente conversacional.

    La memoria **no** vive aqui (esta en el `Store` de LangGraph) ni el conocimiento
    (absorbido por `knowledge_sources` + `agent_sources`).
    """

    __tablename__ = "agents"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(128), nullable=False, unique=True, index=True))
    profile: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    role_key: str | None = Field(
        default=None,
        sa_column=Column(
            String(64),
            ForeignKey("roles.key", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    custom_identity: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    avatar_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: dt.datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )


class AgentSource(SQLModel, table=True):
    """Asociacion N:M entre agentes y fuentes de conocimiento."""

    __tablename__ = "agent_sources"

    agent_id: int = Field(
        sa_column=Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)
    )
    source_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )


class Thread(SQLModel, table=True):
    """Metadatos de hilo para el dashboard. **Cache de UI, no fuente de verdad.**

    `message_count`, `last_preview` y `title` los mantiene el servicio; si discrepan del
    checkpointer, manda el checkpointer (AGENTS.md §3.4). `id` es el `thread_id` que se
    pasa a LangGraph. `last_consolidated_at` es la marca de agua de consolidacion (D7).
    """

    __tablename__ = "threads"
    __table_args__ = (Index("ix_threads_user_updated", "user_id", "updated_at"),)

    id: int | None = Field(default=None, primary_key=True)
    agent_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    title: str = Field(
        default="Nueva conversación",
        sa_column=Column(String(200), nullable=False, server_default="Nueva conversación"),
    )
    created_at: dt.datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )
    updated_at: dt.datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )
    )
    message_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default=text("0")),
    )
    last_preview: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    last_consolidated_at: dt.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
