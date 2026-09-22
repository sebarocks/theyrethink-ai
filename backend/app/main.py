"""Aplicación FastAPI: arranque, healthchecks y (a partir de la Fase 3) routers.

Al importar este módulo no se toca la base de datos ni se ejecuta nada con efectos
secundarios más allá de construir la app.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status

from app.agent.runtime import agent_runtime
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


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=API_VERSION,
        debug=settings.debug,
        lifespan=lifespan,
    )

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
