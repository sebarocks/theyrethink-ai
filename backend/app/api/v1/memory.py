"""Memoria visible y olvidable del usuario (D10).

La memoria vive en el `Store` de LangGraph con namespace `(agente, usuario)` (D1). Aquí solo
se expone la del **usuario autenticado**: leer los hechos aprendidos y olvidarlos de forma
explícita. Borrar un hilo **no** toca la memoria (D10); esto sí.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.service import AgentService
from app.api.deps import CurrentUser, ensure_user_id, get_agent_service
from app.db import get_session
from app.models import Agent, User

router = APIRouter(prefix="/agents", tags=["memory"])


class MemoryFactResponse(BaseModel):
    """Hecho persistente sobre el usuario, tal como lo ve la UI."""

    content: str
    category: str | None = None


class MemoryResponse(BaseModel):
    facts: list[MemoryFactResponse]


def _agent_not_found() -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={
            "error": "not_found",
            "code": "agent_not_found",
            "detail": "El agente no existe.",
        },
    )


@router.get("/{agent_id}/memory", response_model=MemoryResponse)
async def read_memory(
    agent_id: int,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
    service: AgentService = Depends(get_agent_service),  # noqa: B008
) -> MemoryResponse:
    """Hechos que el agente recuerda del usuario autenticado, en orden de inserción."""
    if await db.get(Agent, agent_id) is None:
        raise _agent_not_found()
    facts = await service.read_memory(agent_id=agent_id, user_id=ensure_user_id(user))
    return MemoryResponse(
        facts=[MemoryFactResponse(content=fact.content, category=fact.category) for fact in facts]
    )


@router.delete("/{agent_id}/memory", status_code=status.HTTP_204_NO_CONTENT)
async def forget_memory(
    agent_id: int,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
    service: AgentService = Depends(get_agent_service),  # noqa: B008
) -> None:
    """Olvida toda la memoria del usuario autenticado para ese agente (D10)."""
    if await db.get(Agent, agent_id) is None:
        raise _agent_not_found()
    await service.forget_memory(agent_id=agent_id, user_id=ensure_user_id(user))
