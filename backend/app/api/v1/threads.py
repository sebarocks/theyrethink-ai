"""Metadatos y pertenencia de hilos."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.service import AgentService
from app.api.deps import CurrentUser
from app.db import get_session
from app.models import Thread, User

router = APIRouter(prefix="/threads", tags=["threads"])


class ThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    user_id: int
    title: str
    message_count: int
    last_preview: str
    created_at: datetime
    updated_at: datetime
    last_consolidated_at: datetime | None


class ThreadCreate(BaseModel):
    agent_id: int
    title: str = Field(default="Nueva conversación", max_length=200)


class ThreadUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


def _response(thread: object) -> ThreadResponse:
    return ThreadResponse.model_validate(thread, from_attributes=True)


def _user_id(user: User) -> int:
    if user.id is None:
        raise RuntimeError("El usuario autenticado no tiene id")
    return user.id


def get_agent_service(request: Request) -> AgentService:
    return request.app.state.agent_service


@router.get("", response_model=list[ThreadResponse])
async def list_threads(
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
    service: AgentService = Depends(get_agent_service),  # noqa: B008
) -> list[ThreadResponse]:
    return [_response(thread) for thread in await service.list_threads(db, user_id=_user_id(user))]


@router.post("", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_thread(
    payload: ThreadCreate,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
    service: AgentService = Depends(get_agent_service),  # noqa: B008
) -> ThreadResponse:
    try:
        thread = await service.create_thread(
            db,
            agent_id=payload.agent_id,
            user_id=_user_id(user),
            title=payload.title,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return _response(thread)


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: int,
    payload: ThreadUpdate,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> ThreadResponse:
    thread = await db.get(Thread, thread_id)
    if thread is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "thread_not_found",
                "detail": "El hilo no existe.",
            },
        )
    if thread.user_id != _user_id(user):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "thread_not_found",
                "detail": "El hilo no existe.",
            },
        )
    thread.title = payload.title
    await db.commit()
    await db.refresh(thread)
    return _response(thread)


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: int,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
    service: AgentService = Depends(get_agent_service),  # noqa: B008
) -> None:
    thread = await db.get(Thread, thread_id)
    if thread is None or thread.user_id != _user_id(user):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "thread_not_found",
                "detail": "El hilo no existe.",
            },
        )
    await service.delete_thread(db, thread_id=thread_id)
    await db.commit()
