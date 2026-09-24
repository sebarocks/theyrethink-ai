"""Administración de cuentas de usuario (D17, ADR `0021`).

Solo para administradores. El registro público (D13) crea cuentas con rol `usuario`; este
router es la vía para listarlas, editarlas, cambiarles el rol y borrarlas. La contraseña se
hashea con Argon2 y nunca se expone.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireAdmin, ensure_user_id
from app.db import get_session
from app.models import User
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])

RoleName = Literal["admin", "usuario"]


class UserAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    created_at: datetime


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: RoleName = "usuario"


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: RoleName | None = None


def _not_found() -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={
            "error": "not_found",
            "code": "user_not_found",
            "detail": "El usuario no existe.",
        },
    )


def _conflict(code: str, detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={"error": "conflict", "code": code, "detail": detail},
    )


async def _commit_or_conflict(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict(
            "identity_already_exists", "El usuario o correo ya está registrado."
        ) from exc


async def _ensure_unique(
    db: AsyncSession, *, username: str | None, email: str | None, exclude_id: int | None = None
) -> None:
    candidates = [value for value in (username, email) if value is not None]
    if not candidates:
        return
    query = select(User).where(or_(User.username.in_(candidates), User.email.in_(candidates)))
    if exclude_id is not None:
        query = query.where(User.id != exclude_id)
    if (await db.execute(query)).first() is not None:
        raise _conflict("identity_already_exists", "El usuario o correo ya está registrado.")


@router.get("", response_model=list[UserAdminResponse])
async def list_users(
    _admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[User]:
    return list((await db.execute(select(User).order_by(User.username))).scalars())


@router.post("", response_model=UserAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    _admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    await _ensure_unique(db, username=payload.username, email=payload.email)
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await _commit_or_conflict(db)
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserAdminResponse)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise _not_found()
    admin_id = ensure_user_id(admin)
    changes = payload.model_dump(exclude_unset=True)
    if user_id == admin_id and changes.get("role", "admin") != "admin":
        raise _conflict("cannot_modify_self", "No puedes quitarte tu propio rol de administrador.")
    await _ensure_unique(
        db,
        username=changes.get("username"),
        email=changes.get("email"),
        exclude_id=user_id,
    )
    if "password" in changes:
        user.password_hash = hash_password(changes["password"])
    for field in ("username", "email", "role"):
        if field in changes:
            setattr(user, field, changes[field])
    await _commit_or_conflict(db)
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    admin: User = RequireAdmin,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    if user_id == ensure_user_id(admin):
        raise _conflict("cannot_modify_self", "No puedes eliminar tu propia cuenta.")
    user = await db.get(User, user_id)
    if user is None:
        raise _not_found()
    await db.delete(user)
    await db.commit()
