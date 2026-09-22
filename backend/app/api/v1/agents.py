"""Consulta, administración y avatares de agentes."""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, RequireAdmin
from app.config import get_settings
from app.db import get_session
from app.models import Agent, User

router = APIRouter(prefix="/agents", tags=["agents"])
MAX_AVATAR_BYTES = 5 * 1024 * 1024
_AVATAR_TYPES = {
    "image/jpeg": (b"\\xff\\xd8\\xff", ".jpg"),
    "image/png": (b"\\x89PNG\\r\\n\\x1a\\n", ".png"),
    "image/gif": (b"GIF8", ".gif"),
    "image/webp": (b"RIFF", ".webp"),
}


def _avatar_error(
    code: str,
    detail: str,
    http_status: int = status.HTTP_400_BAD_REQUEST,
) -> HTTPException:
    return HTTPException(
        http_status,
        detail={"error": "avatar_error", "code": code, "detail": detail},
    )


def _agent_not_found() -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={
            "error": "not_found",
            "code": "agent_not_found",
            "detail": "El agente no existe.",
        },
    )


def _avatar_not_found() -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={
            "error": "not_found",
            "code": "avatar_not_found",
            "detail": "El agente no tiene avatar.",
        },
    )


def _avatar_directory() -> Path:
    directory = Path(get_settings().avatar_storage_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _avatar_path(agent: Agent) -> Path | None:
    if not agent.avatar_url:
        return None
    path = _avatar_directory() / Path(agent.avatar_url).name
    return path if path.is_file() else None


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    profile: str
    role_key: str | None
    custom_identity: str | None
    avatar_url: str | None


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    profile: str = ""
    role_key: str | None = None
    custom_identity: str | None = None


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    _user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[Agent]:
    return list((await db.execute(select(Agent).order_by(Agent.name))).scalars())


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    _user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> Agent:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "agent_not_found",
                "detail": "El agente no existe.",
            },
        )
    return agent


@router.post("/{agent_id}/avatar", response_model=AgentResponse)
async def upload_avatar(
    agent_id: int,
    file: UploadFile = File(...),  # noqa: B008
    _admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> Agent:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise _agent_not_found()
    if file.content_type not in _AVATAR_TYPES:
        raise _avatar_error("unsupported_type", "Solo se aceptan JPEG, PNG, GIF y WEBP.")
    content = await file.read(MAX_AVATAR_BYTES + 1)
    if len(content) > MAX_AVATAR_BYTES:
        raise _avatar_error("file_too_large", "El avatar supera el límite de 5 MiB.")
    signature, extension = _AVATAR_TYPES[file.content_type]
    if not content.startswith(signature):
        raise _avatar_error("invalid_content", "El contenido no coincide con su tipo declarado.")

    destination = _avatar_directory() / f"{uuid4().hex}{extension}"
    destination.write_bytes(content)
    old_path = _avatar_path(agent)
    agent.avatar_url = destination.name
    await db.commit()
    await db.refresh(agent)
    if old_path is not None and old_path != destination:
        old_path.unlink(missing_ok=True)
    return agent


@router.get("/{agent_id}/avatar")
async def download_avatar(
    agent_id: int,
    _user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> FileResponse:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise _agent_not_found()
    path = _avatar_path(agent)
    if path is None:
        raise _avatar_not_found()
    media_type = next(
        media for media, (_, extension) in _AVATAR_TYPES.items() if extension == path.suffix
    )
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@router.delete("/{agent_id}/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar(
    agent_id: int,
    _admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise _agent_not_found()
    path = _avatar_path(agent)
    agent.avatar_url = None
    await db.commit()
    if path is not None:
        path.unlink(missing_ok=True)


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    _admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> Agent:
    agent = Agent(**payload.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent
