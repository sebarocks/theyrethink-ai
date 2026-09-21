"""Modelos de dominio. Importar este paquete registra el metadata para Alembic."""

from app.models.domain import (
    Agent,
    AgentSource,
    KnowledgeSource,
    Role,
    Thread,
    User,
)

__all__ = [
    "Agent",
    "AgentSource",
    "KnowledgeSource",
    "Role",
    "Thread",
    "User",
]
