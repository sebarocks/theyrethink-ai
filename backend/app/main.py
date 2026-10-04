"""Aplicación FastAPI: arranque, healthchecks y (a partir de la Fase 3) routers.

Al importar este módulo no se toca la base de datos ni se ejecuta nada con efectos
secundarios más allá de construir la app.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import metrics
from app.agent.runtime import agent_runtime
from app.api.v1.admin import router as admin_router
from app.api.v1.agents import router as agents_router
from app.api.v1.auth import router as auth_router
from app.api.v1.catalogs import router as catalogs_router
from app.api.v1.chat import router as chat_router
from app.api.v1.memory import router as memory_router
from app.api.v1.threads import router as threads_router
from app.api.v1.users import router as users_router
from app.config import get_settings
from app.db import ping_database
from app.logging_config import configure_logging, request_id_var
from app.security.csrf import origin_rejection_reason
from app.spa import mount_spa

API_VERSION = "0.1.0"
_logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Ciclo de vida de la aplicacion.

    Fase 2: crea el checkpointer y el `Store` de LangGraph (`setup()` idempotente), compila
    los grafos una sola vez y arranca el worker de consolidacion. El servicio queda en
    `app.state.agent_service` para los routers de la Fase 3.
    """
    async with agent_runtime() as service:
        app.state.agent_service = service
        yield


def _error_response(
    status_code: int, detail: object, headers: dict[str, str] | None = None
) -> JSONResponse:
    if isinstance(detail, dict) and {"error", "code", "detail"} <= detail.keys():
        payload = detail
    else:
        payload = {
            "error": "request_error",
            "code": "http_error",
            "detail": detail,
        }
    return JSONResponse(status_code=status_code, content=payload, headers=headers)


def _validation_detail(exc: RequestValidationError) -> list[dict[str, object]]:
    """Errores de validación sin el valor enviado.

    El `input` de Pydantic refleja el dato recibido —incluida una contraseña— y termina en
    logs y trazas; el cliente no lo necesita para corregir.
    """
    return jsonable_encoder(
        [
            {key: value for key, value in error.items() if key not in {"input", "url"}}
            for error in exc.errors()
        ]
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    app = FastAPI(
        title=settings.app_name,
        version=API_VERSION,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Se registra sobre la excepción de Starlette (padre de la de FastAPI): así también
    # caen aquí los 404/405 que genera el router, que si no escapan al envelope.
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # `exc.headers` conserva cabeceras como `Retry-After` del límite de peticiones.
        return _error_response(exc.status_code, exc.detail, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "error": "validation_error",
                "code": "invalid_request",
                "detail": _validation_detail(exc),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        """Último recurso: envelope estable sin filtrar el detalle interno."""
        _logger.exception("error no controlado", exc_info=exc)
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            {
                "error": "internal_error",
                "code": "internal_error",
                "detail": "Error interno del servidor.",
            },
        )

    @app.middleware("http")
    async def csrf_origin_guard(request: Request, call_next):
        """Segunda barrera CSRF: `Origin`/`Referer` en métodos no seguros (D24, ADR `0027`)."""
        reason = origin_rejection_reason(request, settings.allowed_origins)
        if reason is not None:
            return _error_response(
                status.HTTP_403_FORBIDDEN,
                {"error": "csrf_error", "code": "origin_not_allowed", "detail": reason},
            )
        return await call_next(request)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        """Correlación por `request_id` (D25, ADR `0028`).

        Se registra después del guard CSRF para ser el middleware **más externo**: así el id
        también aparece en los logs de una petición rechazada por origen.
        """
        request_id = request.headers.get("x-request-id") or uuid4().hex
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-Id"] = request_id
        return response

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(memory_router, prefix="/api/v1")
    app.include_router(catalogs_router, prefix="/api/v1")
    app.include_router(threads_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")

    @app.get("/healthz", tags=["operational"], summary="Proceso vivo")
    async def healthz() -> dict[str, str]:
        """No toca dependencias: responde mientras el proceso esté en pie."""
        return {"status": "ok"}

    @app.get("/readyz", tags=["operational"], summary="Listo para servir tráfico")
    async def readyz() -> dict[str, str]:
        """Depende de la base de datos."""
        if not await ping_database():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="database unavailable",
            )
        return {"status": "ok", "database": "up"}

    @app.get(
        "/metrics", tags=["operational"], summary="Métricas Prometheus", include_in_schema=False
    )
    async def metrics_endpoint(request: Request) -> PlainTextResponse:
        """Registro de métricas del proceso (D25, ADR `0028`).

        Desactivado por defecto. Con `METRICS_TOKEN`, exige `Authorization: Bearer`.
        """
        if not settings.metrics_enabled:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="metrics disabled")
        if settings.metrics_token and (
            request.headers.get("authorization") != f"Bearer {settings.metrics_token}"
        ):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="invalid metrics token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")

    # D4: sirve la SPA construida en el mismo origen. Va al final para que las rutas de API,
    # healthchecks y docs tengan prioridad sobre el montaje de `/`.
    mount_spa(app)

    return app


app = create_app()
