"""Dependencias compartidas de la API y autenticación por sesión."""

from datetime import UTC, datetime
from hashlib import sha256

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Session, User

SESSION_COOKIE = "theyrethink_session"


def auth_error(
    code: str, detail: str, http_status: int = status.HTTP_401_UNAUTHORIZED
) -> HTTPException:
    """Construye el formato de error público estable de la API."""
    return HTTPException(
        status_code=http_status,
        detail={"error": "authentication_error", "code": code, "detail": detail},
    )


def hash_session_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


async def get_current_user(
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    """Resuelve una sesión activa y devuelve su usuario."""
    if not token:
        raise auth_error("authentication_required", "Se requiere una sesión válida.")
    result = await db.execute(
        select(Session, User)
        .join(User, User.id == Session.user_id)
        .where(
            Session.token_hash == hash_session_token(token),
            Session.revoked_at.is_(None),
            Session.expires_at > datetime.now(UTC),
        )
    )
    row = result.one_or_none()
    if row is None:
        raise auth_error("invalid_session", "La sesión no es válida o ha expirado.")
    return row[1]


CurrentUser = Depends(get_current_user)


async def require_admin(user: User = CurrentUser) -> User:
    """Exige una sesión válida con rol administrador."""
    if user.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "error": "authorization_error",
                "code": "admin_required",
                "detail": "Se requiere rol administrador.",
            },
        )
    return user


RequireAdmin = Depends(require_admin)


def ensure_user_id(user: User) -> int:
    """Devuelve el id de una entidad persistida autenticada."""
    if user.id is None:
        raise RuntimeError("El usuario autenticado no tiene id")
    return user.id
