"""Servido de la SPA construida (D4, ADR `0011`/`0015`).

En producción FastAPI sirve el build de `adapter-static` en el **mismo origen** que `/api/v1`
(sin CORS). En desarrollo el frontend corre en Vite y este montaje no existe, porque el
directorio de build no está: el montaje se activa solo si hay `index.html`.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope

from app.config import get_settings

FALLBACK_FILE = "200.html"


def default_dist_dir() -> Path:
    """`frontend/build` del repo, resuelto desde la ubicación de este archivo."""
    return Path(__file__).resolve().parents[2] / "frontend" / "build"


def spa_directory() -> Path | None:
    """Directorio del build de la SPA, o `None` si no hay build (modo desarrollo)."""
    configured = get_settings().frontend_dist_dir
    directory = Path(configured) if configured else default_dist_dir()
    return directory if (directory / "index.html").is_file() else None


class SPAStaticFiles(StaticFiles):
    """Estáticos con *fallback* de SPA: lo desconocido devuelve el shell, no un 404.

    `/api/...` queda excluido: una ruta de API inexistente debe ser un 404 real, no el shell.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response(FALLBACK_FILE, scope)


def mount_spa(app: FastAPI) -> bool:
    """Monta la SPA en `/` si hay build. Devuelve si se montó.

    Debe llamarse **después** de registrar routers y rutas: Starlette resuelve en orden, así
    que `/api/v1`, `/healthz`, `/docs` y `/openapi.json` tienen prioridad sobre el montaje.
    """
    directory = spa_directory()
    if directory is None:
        return False
    app.mount("/", SPAStaticFiles(directory=directory, html=True), name="spa")
    return True
