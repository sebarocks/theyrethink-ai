"""Modelos de dominio. Importar este paquete registra el metadata para Alembic."""

from app.models.domain import (
    Agent,
    AgentSource,
    ConsolidationJob,
    KnowledgeSource,
    Role,
    Session,
    Thread,
    User,
)

__all__ = [
    "Agent",
    "AgentSource",
    "ConsolidationJob",
    "KnowledgeSource",
    "Role",
    "Session",
    "Thread",
    "User",
]
