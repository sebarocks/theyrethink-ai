#!/bin/sh
# Restaura un backup custom de Postgres en una base **destino** (Fase 6, ADR 0025).
#
# Por defecto NO toca la base de producción: restaura en `theyrethink_restore`, que es lo que
# permite ensayar el restore sin riesgo. Para restaurar sobre otra base hay que pasarla
# explícitamente como segundo argumento.
#
# Uso:
#   ./backend/scripts/restore_postgres.sh backups/theyrethink-20261002T120000Z.dump
#   ./backend/scripts/restore_postgres.sh <dump> mi_base_destino
set -eu

if [ "$#" -lt 1 ]; then
    echo "uso: $0 <archivo.dump> [base_destino]" >&2
    exit 2
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_ROOT/docker-compose.prod.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
DUMP="$1"
TARGET_DB="${2:-theyrethink_restore}"

if [ ! -s "$DUMP" ]; then
    echo "restore: no existe el backup $DUMP" >&2
    exit 2
fi

# Base limpia: el ensayo debe reproducir un restore desde cero, no un *merge*.
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" sh -c \
    "dropdb --if-exists -U \"\$POSTGRES_USER\" '$TARGET_DB' && createdb -U \"\$POSTGRES_USER\" '$TARGET_DB'"

docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" sh -c \
    "pg_restore -U \"\$POSTGRES_USER\" -d '$TARGET_DB' --no-owner --exit-on-error" <"$DUMP"

echo "restore: $DUMP -> base '$TARGET_DB'"
