"""Dependencias compartidas de la API y autenticación por sesión."""

from datetime import UTC, datetime
from hashlib import sha256

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.service import AgentService
from app.config import get_settings
from app.db import get_session
from app.models import Session, User
from app.security.rate_limit import RateLimitExceeded, enforce_rate_limit

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


def get_agent_service(request: Request) -> AgentService:
    """Núcleo del agente montado en el `lifespan` (la costura, ADR `0006`)."""
    return request.app.state.agent_service


AgentServiceDep = Depends(get_agent_service)


def _client_ip(request: Request) -> str:
    """IP del cliente. No se lee `X-Forwarded-For` salvo que `uvicorn` esté configurado para
    confiar en el proxy (`FORWARDED_ALLOW_IPS`): si no, la cabecera es falsificable y el límite
    por IP se podría eludir (ADR `0026`)."""
    return request.client.host if request.client else "unknown"


def _too_many_requests(exc: RateLimitExceeded) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "error": "rate_limit_exceeded",
            "code": "too_many_requests",
            "detail": "Demasiadas peticiones. Inténtalo de nuevo más tarde.",
        },
        headers={"Retry-After": str(exc.retry_after)},
    )


async def auth_rate_limit(
    request: Request,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    """Limita por IP los intentos de `/auth/login` y `/auth/register` (D23, ADR `0026`)."""
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    try:
        await enforce_rate_limit(
            db,
            scope="auth",
            key=_client_ip(request),
            limit=settings.rate_limit_auth_attempts,
            window_seconds=settings.rate_limit_auth_window_seconds,
        )
    except RateLimitExceeded as exc:
        raise _too_many_requests(exc) from exc


async def chat_rate_limit(
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    """Limita por usuario el envío de mensajes de chat (D23, ADR `0026`)."""
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    try:
        await enforce_rate_limit(
            db,
            scope="chat",
            key=str(ensure_user_id(user)),
            limit=settings.rate_limit_chat_attempts,
            window_seconds=settings.rate_limit_chat_window_seconds,
        )
    except RateLimitExceeded as exc:
        raise _too_many_requests(exc) from exc


AuthRateLimit = Depends(auth_rate_limit)
ChatRateLimit = Depends(chat_rate_limit)
