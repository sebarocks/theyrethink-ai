# syntax=docker/dockerfile:1
# Imagen de producción (D22, ADR 0025).
#
# Tres etapas: la SPA se construye con Deno (que queda **solo** en build-time, D8/ADR 0018),
# las dependencias de Python se resuelven con uv contra el lockfile versionado, y la imagen
# final solo lleva el runtime de Python + el backend + el build estático. Sin Node ni Deno.

# ---------------------------------------------------------------------------- SPA (Deno)
FROM denoland/deno:2.9.7 AS spa

USER root
WORKDIR /app/frontend

# Manifiesto primero: la capa de dependencias se cachea mientras no cambie el lockfile.
COPY frontend/deno.json frontend/deno.lock ./
RUN deno install --frozen

COPY frontend/ ./
# `vite build` compila los mensajes de Paraglide y genera `build/` con `200.html`.
RUN deno task build

# ------------------------------------------------------------- dependencias (uv + lockfile)
# El tag `ghcr.io/astral-sh/uv` solo trae el binario (sin shell), así que se copia sobre una
# base Python normal para poder ejecutar `uv sync`.
FROM python:3.13-slim AS python-deps

COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# ------------------------------------------------------------------------------- runtime
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    PATH="/app/backend/.venv/bin:${PATH}"

WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --home /app app

# `psycopg` (checkpointer y Store de LangGraph) necesita libpq en runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=python-deps --chown=app:app /app/backend/.venv /app/backend/.venv
COPY --chown=app:app backend/ /app/backend/
COPY --from=spa --chown=app:app /app/frontend/build /app/frontend/build

# Volumen de avatares (D12/ADR 0017): el contenedor no guarda estado que importe. El `chmod`
# cubre umasks restrictivos del host de build: `app` necesita leer el código, el venv y la SPA.
RUN mkdir -p /app/backend/var/avatars \
    && chmod -R a+rX /app/backend /app/frontend \
    && chown -R app:app /app/backend/var
USER app

EXPOSE 8000
# Liveness: no toca dependencias. El orquestador debe usar `/readyz` para enrutar tráfico.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"

WORKDIR /app/backend
CMD ["/app/backend/scripts/serve.sh"]
