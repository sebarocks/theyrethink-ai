"""Endpoints públicos de registro y autenticación por cookie revocable."""

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SESSION_COOKIE, CurrentUser, auth_error, hash_session_token
from app.db import get_session
from app.models import Session, User
from app.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
SESSION_DAYS = 30


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str


async def _create_session(response: Response, user: User, db: AsyncSession) -> None:
    token = secrets.token_urlsafe(32)
    db.add(
        Session(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=SESSION_DAYS),
        )
    )
    await db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=SESSION_DAYS * 86400,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    """Registra un usuario normal y crea su sesión."""
    result = await db.execute(
        select(User).where(or_(User.username == payload.username, User.email == payload.email))
    )
    if result.scalar_one_or_none() is not None:
        raise auth_error(
            "identity_already_exists",
            "El usuario o correo ya está registrado.",
            status.HTTP_409_CONFLICT,
        )
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()
    await _create_session(response, user, db)
    await db.refresh(user)
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    """Autentica por nombre de usuario y crea una sesión."""
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(user.password_hash, payload.password):
        raise auth_error("invalid_credentials", "Las credenciales no son válidas.")
    await _create_session(response, user, db)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    """Revoca todas las sesiones activas del usuario y borra la cookie."""
    result = await db.execute(
        select(Session).where(Session.user_id == user.id, Session.revoked_at.is_(None))
    )
    for session in result.scalars():
        session.revoked_at = datetime.now(UTC)
    await db.commit()
    response.delete_cookie(SESSION_COOKIE)


@router.get("/me", response_model=UserResponse)
async def me(user: User = CurrentUser) -> User:
    """Devuelve la identidad autenticada."""
    return user
