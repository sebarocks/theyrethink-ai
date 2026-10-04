#!/bin/sh
# Backup lógico de Postgres en formato custom (Fase 6, ADR 0025).
#
# Requisito del DoD de la Fase 6: el backup solo cuenta si se ha ensayado un restore
# (ver `docs/backup-restore.md`).
#
# Uso:
#   ./backend/scripts/backup_postgres.sh
#   COMPOSE_FILE=docker-compose.yml BACKUP_DIR=/tmp/b ./backend/scripts/backup_postgres.sh
#
# Variables:
#   COMPOSE_FILE            (por defecto docker-compose.prod.yml)
#   POSTGRES_SERVICE        (por defecto postgres)
#   BACKUP_DATABASE         (por defecto la base del contenedor: POSTGRES_DB)
#   BACKUP_DIR              (por defecto <repo>/backups)
#   BACKUP_RETENTION_DAYS   (por defecto 14; 0 desactiva la purga)
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_ROOT/docker-compose.prod.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
BACKUP_DATABASE="${BACKUP_DATABASE:-}"
BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
TARGET="$BACKUP_DIR/theyrethink-$STAMP.dump"

# `pg_dump` corre dentro del contenedor de Postgres: no hace falta cliente en el host.
# `BACKUP_DATABASE` permite respaldar otra base (p. ej. staging) con el mismo script.
docker compose -f "$COMPOSE_FILE" exec -T -e "BACKUP_DATABASE=$BACKUP_DATABASE" "$POSTGRES_SERVICE" \
    sh -c 'pg_dump -U "$POSTGRES_USER" -d "${BACKUP_DATABASE:-$POSTGRES_DB}" --format=custom --no-owner' >"$TARGET"

if [ ! -s "$TARGET" ]; then
    echo "backup: el archivo quedó vacío, revisa la conexión y el nombre de la base" >&2
    exit 1
fi

if [ "$BACKUP_RETENTION_DAYS" -gt 0 ]; then
    find "$BACKUP_DIR" -maxdepth 1 -name 'theyrethink-*.dump' -type f \
        -mtime "+$BACKUP_RETENTION_DAYS" -delete
fi

echo "backup: $TARGET ($(wc -c <"$TARGET") bytes)"
