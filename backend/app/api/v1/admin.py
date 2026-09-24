"""Vista de administración de conversaciones (D18, ADR `0021`).

Solo para administradores. Lista **todas** las conversaciones y permite leer cualquier
transcript. La lectura se hace por `agent/service.py` (D16); este router no conoce el
checkpointer (`AGENTS.md` §3.1/§3.3).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.service import AgentService
from app.api.deps import RequireAdmin
from app.api.v1.chat import MessageResponse
from app.db import get_session
from app.models import Agent, Thread, User

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminThreadResponse(BaseModel):
    id: int
    agent_id: int
    agent_name: str
    user_id: int
    username: str
    title: str
    message_count: int
    last_preview: str
    created_at: datetime
    updated_at: datetime


def get_agent_service(request: Request) -> AgentService:
    return request.app.state.agent_service


def _thread_not_found() -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={
            "error": "not_found",
            "code": "thread_not_found",
            "detail": "El hilo no existe.",
        },
    )


@router.get("/threads", response_model=list[AdminThreadResponse])
async def list_all_threads(
    _admin: User = RequireAdmin,
    agent_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[AdminThreadResponse]:
    query = (
        select(Thread, Agent.name, User.username)
        .join(Agent, Agent.id == Thread.agent_id)
        .join(User, User.id == Thread.user_id)
        .order_by(Thread.updated_at.desc(), Thread.id.desc())
    )
    if agent_id is not None:
        query = query.where(Thread.agent_id == agent_id)
    rows = (await db.execute(query)).all()
    return [
        AdminThreadResponse(
            id=thread.id or 0,
            agent_id=thread.agent_id,
            agent_name=agent_name,
            user_id=thread.user_id,
            username=username,
            title=thread.title,
            message_count=thread.message_count,
            last_preview=thread.last_preview,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
        )
        for thread, agent_name, username in rows
    ]


@router.get("/threads/{thread_id}/messages", response_model=list[MessageResponse])
async def list_thread_messages(
    thread_id: int,
    _admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
    service: AgentService = Depends(get_agent_service),  # noqa: B008
) -> list[MessageResponse]:
    """Transcript de cualquier hilo, leído del checkpointer (D16/D18)."""
    if await db.get(Thread, thread_id) is None:
        raise _thread_not_found()
    messages = await service.read_messages(thread_id=thread_id)
    return [MessageResponse(role=message.role, text=message.text) for message in messages]
