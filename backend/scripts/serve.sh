#!/bin/sh
# Arranque del servidor de producción (D22, ADR 0025).
#
# Las migraciones NO se ejecutan aquí: son un paso de release aparte y anterior
# (`alembic upgrade head`). Ver `docs/operations.md`.
set -eu

WORKERS="${WEB_CONCURRENCY:-$(nproc)}"

set -- uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "$WORKERS" \
    --timeout-graceful-shutdown "${GRACEFUL_SHUTDOWN_SECONDS:-30}"

# Detrás de un proxy de confianza hay que activarlo explícitamente: sin esto, `request.client`
# es el proxy y el límite por IP no distingue clientes. No se activa por defecto porque
# `X-Forwarded-For` es falsificable si no hay un proxy que lo sanee (ADR 0026).
if [ -n "${FORWARDED_ALLOW_IPS:-}" ]; then
    set -- "$@" --proxy-headers --forwarded-allow-ips "$FORWARDED_ALLOW_IPS"
fi

exec "$@"
