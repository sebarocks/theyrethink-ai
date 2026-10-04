"""Endpoints públicos de registro y autenticación por cookie revocable."""

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    SESSION_COOKIE,
    AuthRateLimit,
    CurrentUser,
    auth_error,
    hash_session_token,
)
from app.config import get_settings
from app.db import get_session
from app.models import Session, User
from app.security import hash_password, needs_rehash, verify_password
from app.security.policy import password_policy_error

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def _check_password_policy(self) -> "RegisterRequest":
        """Aplica D24 (longitud configurable + no reutilizar la identidad)."""
        reason = password_policy_error(self.password, username=self.username, email=self.email)
        if reason:
            raise ValueError(reason)
        return self


class LoginRequest(BaseModel):
    username: str
    password: str


class ProfileUpdate(BaseModel):
    """Edición del perfil propio (D19). El rol no se cambia aquí (eso es D17)."""

    username: str | None = Field(default=None, min_length=3, max_length=64)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str


async def _create_session(response: Response, user: User, db: AsyncSession) -> None:
    """Emite una sesión nueva y rota la cookie (anti-fijación, D24/ADR `0027`).

    El token es CSPRNG y se genera en cada login: el cliente nunca elige el identificador de
    sesión. Los flags de la cookie salen de configuración, con `Secure` activo por defecto.
    """
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    db.add(
        Session(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.session_days),
        )
    )
    await db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        domain=settings.session_cookie_domain,
        max_age=settings.session_days * 86400,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    _rate: None = AuthRateLimit,
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
    _rate: None = AuthRateLimit,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    """Autentica por nombre de usuario y crea una sesión."""
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(user.password_hash, payload.password):
        raise auth_error("invalid_credentials", "Las credenciales no son válidas.")
    if needs_rehash(user.password_hash):
        # Re-hash perezoso: el hash heredado de Werkzeug (migración Fase 5) se reescribe a
        # Argon2 en el primer login exitoso, con la contraseña ya verificada en claro.
        user.password_hash = hash_password(payload.password)
        await db.commit()
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


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: ProfileUpdate,
    request: Request,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    """Actualiza el perfil propio (D19): nombre, correo y/o contraseña."""
    if payload.username is not None or payload.email is not None:
        conditions = []
        if payload.username is not None:
            conditions.append(User.username == payload.username)
        if payload.email is not None:
            conditions.append(User.email == payload.email)
        query = select(User).where(or_(*conditions), User.id != user.id)
        if (await db.execute(query)).first() is not None:
            raise auth_error(
                "identity_already_exists",
                "El usuario o correo ya está registrado.",
                status.HTTP_409_CONFLICT,
            )
    if payload.new_password is not None:
        if payload.current_password is None or not verify_password(
            user.password_hash, payload.current_password
        ):
            raise auth_error(
                "invalid_current_password",
                "La contraseña actual no es válida.",
                status.HTTP_400_BAD_REQUEST,
            )
        reason = password_policy_error(
            payload.new_password,
            username=payload.username or user.username,
            email=payload.email or user.email,
        )
        if reason:
            raise auth_error("weak_password", reason, status.HTTP_422_UNPROCESSABLE_CONTENT)
        user.password_hash = hash_password(payload.new_password)
    if payload.username is not None:
        user.username = payload.username
    if payload.email is not None:
        user.email = payload.email
    if payload.new_password is not None:
        # Anti-fijación (D24): al cambiar la contraseña se cierran las demás sesiones, no la
        # que hace el cambio.
        current_hash = hash_session_token(request.cookies.get(SESSION_COOKIE, ""))
        sessions = await db.execute(
            select(Session).where(
                Session.user_id == user.id,
                Session.revoked_at.is_(None),
                Session.token_hash != current_hash,
            )
        )
        for session in sessions.scalars():
            session.revoked_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(user)
    return user
