"""Aplicación FastAPI: arranque, healthchecks y (a partir de la Fase 3) routers.

Al importar este módulo no se toca la base de datos ni se ejecuta nada con efectos
secundarios más allá de construir la app.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status

from app.config import get_settings
from app.db import ping_database

API_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Ciclo de vida de la aplicación.

    Fase 2: aquí se crean el checkpointer y el `Store` de LangGraph (`await setup()`).
    """
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
