"""Catálogos y administración de roles y fuentes de conocimiento."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, RequireAdmin
from app.db import get_session
from app.models import Agent, AgentSource, KnowledgeSource, Role, User

router = APIRouter(tags=["catalogs"])


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name: str
    description: str
    prompt: str
    is_system: bool


class RoleCreate(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    prompt: str = ""
    is_system: bool = False


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    prompt: str | None = None
    is_system: bool | None = None


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    content: str


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    content: str = ""


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = None


class AgentSourceResponse(BaseModel):
    agent_id: int
    source_id: int


def _not_found(code: str, detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={"error": "not_found", "code": code, "detail": detail},
    )


def _conflict(code: str, detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={"error": "conflict", "code": code, "detail": detail},
    )


async def _commit_or_conflict(db: AsyncSession, code: str, detail: str) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict(code, detail) from exc


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    _user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[Role]:
    return list((await db.execute(select(Role).order_by(Role.name))).scalars())


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    _admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> Role:
    role = Role(**payload.model_dump())
    db.add(role)
    await _commit_or_conflict(db, "role_key_taken", "La clave del rol ya existe.")
    await db.refresh(role)
    return role


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    payload: RoleUpdate,
    _admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> Role:
    role = await db.get(Role, role_id)
    if role is None:
        raise _not_found("role_not_found", "El rol no existe.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(role, key, value)
    await _commit_or_conflict(db, "role_update_conflict", "No se pudo actualizar el rol.")
    await db.refresh(role)
    return role


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    _admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    role = await db.get(Role, role_id)
    if role is None:
        raise _not_found("role_not_found", "El rol no existe.")
    await db.delete(role)
    await db.commit()


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(
    _user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[KnowledgeSource]:
    return list(
        (await db.execute(select(KnowledgeSource).order_by(KnowledgeSource.name))).scalars()
    )


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    _admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> KnowledgeSource:
    source = KnowledgeSource(**payload.model_dump())
    db.add(source)
    await _commit_or_conflict(db, "source_name_taken", "El nombre de la fuente ya existe.")
    await db.refresh(source)
    return source


@router.patch("/sources/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int,
    payload: SourceUpdate,
    _admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> KnowledgeSource:
    source = await db.get(KnowledgeSource, source_id)
    if source is None:
        raise _not_found("source_not_found", "La fuente no existe.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, key, value)
    await _commit_or_conflict(db, "source_update_conflict", "No se pudo actualizar la fuente.")
    await db.refresh(source)
    return source


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    _admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    source = await db.get(KnowledgeSource, source_id)
    if source is None:
        raise _not_found("source_not_found", "La fuente no existe.")
    await db.delete(source)
    await db.commit()


@router.get("/agents/{agent_id}/sources", response_model=list[SourceResponse])
async def list_agent_sources(
    agent_id: int,
    _user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[KnowledgeSource]:
    """Fuentes asociadas a un agente; alimenta el editor del dashboard (D18)."""
    if await db.get(Agent, agent_id) is None:
        raise _not_found("agent_not_found", "El agente no existe.")
    return list(
        (
            await db.execute(
                select(KnowledgeSource)
                .join(AgentSource, AgentSource.source_id == KnowledgeSource.id)
                .where(AgentSource.agent_id == agent_id)
                .order_by(KnowledgeSource.name)
            )
        ).scalars()
    )


@router.put("/agents/{agent_id}/sources/{source_id}", response_model=AgentSourceResponse)
async def attach_source(
    agent_id: int,
    source_id: int,
    _admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> AgentSource:
    if await db.get(Agent, agent_id) is None:
        raise _not_found("agent_not_found", "El agente no existe.")
    if await db.get(KnowledgeSource, source_id) is None:
        raise _not_found("source_not_found", "La fuente no existe.")
    link = AgentSource(agent_id=agent_id, source_id=source_id)
    db.add(link)
    await _commit_or_conflict(
        db,
        "source_already_attached",
        "La fuente ya está asociada al agente.",
    )
    return link


@router.delete("/agents/{agent_id}/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_source(
    agent_id: int,
    source_id: int,
    _admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    link = (
        await db.execute(
            select(AgentSource).where(
                AgentSource.agent_id == agent_id,
                AgentSource.source_id == source_id,
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise _not_found("source_attachment_not_found", "La asociación no existe.")
    await db.delete(link)
    await db.commit()
