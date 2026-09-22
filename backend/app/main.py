"""Aplicación FastAPI: arranque, healthchecks y (a partir de la Fase 3) routers.

Al importar este módulo no se toca la base de datos ni se ejecuta nada con efectos
secundarios más allá de construir la app.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.agent.runtime import agent_runtime
from app.api.v1.agents import router as agents_router
from app.api.v1.auth import router as auth_router
from app.api.v1.catalogs import router as catalogs_router
from app.api.v1.chat import router as chat_router
from app.api.v1.threads import router as threads_router
from app.config import get_settings
from app.db import ping_database

API_VERSION = "0.1.0"


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


def _error_response(status_code: int, detail: object) -> JSONResponse:
    if isinstance(detail, dict) and {"error", "code", "detail"} <= detail.keys():
        payload = detail
    else:
        payload = {
            "error": "request_error",
            "code": "http_error",
            "detail": detail,
        }
    return JSONResponse(status_code=status_code, content=payload)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=API_VERSION,
        debug=settings.debug,
        lifespan=lifespan,
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return _error_response(exc.status_code, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "error": "validation_error",
                "code": "invalid_request",
                "detail": exc.errors(),
            },
        )

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(catalogs_router, prefix="/api/v1")
    app.include_router(threads_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")

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

    return app


app = create_app()
