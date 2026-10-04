# theyrethink-ai

Reescritura de la plataforma THEYTHINK AI: backend FastAPI con el núcleo agéntico sobre
LangGraph, y frontend SvelteKit sobre Deno.

> El proyecto anterior (`../theythink-ai`) se conserva como **referencia de features y datos,
> solo lectura**.

## Documentación

| Documento | Rol |
|---|---|
| [`REWRITE_PROPOSAL.md`](./REWRITE_PROPOSAL.md) | Arquitectura y decisiones (registro canónico: §14) |
| [`DEVELOPMENT_PLAN.md`](./DEVELOPMENT_PLAN.md) | Fases, DoD, gates y estado |
| [`AGENTS.md`](./AGENTS.md) | Reglas obligatorias de toolchain y arquitectura |
| [`docs/adr/`](./docs/adr/) | Architecture Decision Records |
| [`docs/spikes/`](./docs/spikes/) | Spikes técnicos y sus conclusiones |
| [`docs/operations.md`](./docs/operations.md) | Despliegue, escalado y observabilidad |
| [`docs/backup-restore.md`](./docs/backup-restore.md) | Backups y ensayo de restore |
| [`docs/runbook-cutover.md`](./docs/runbook-cutover.md) | Corte, rollback y archivo del proyecto viejo |

## Toolchain

- **Python:** `uv` (Astral).
- **Frontend:** SvelteKit (Deno)

Detalle y comandos en [`AGENTS.md`](./AGENTS.md).

## Arranque rápido

`make` es opcional: cada objetivo delega en el comando directo.

| Operación | Comando directo | Comando `make` |
|---|---|---|
| Levantar Postgres | `docker compose up -d postgres` | `make db` |
| Aplicar migraciones | `cd backend && uv run alembic upgrade head` | `make migrate` |
| Sembrar datos canónicos | `cd backend && uv run python -m app.seed` | `make seed` |
| Levantar la API en desarrollo | `cd backend && uv run uvicorn app.main:app --reload` | `make dev` |

API en `http://localhost:8000` · `/healthz` · `/readyz` · `/docs`.

Antes de ejecutar, copia `backend/.env.example` a `backend/.env` y **genera una
`SECRET_KEY` propia** (`openssl rand -hex 32`). No hay valor por defecto: la aplicación no
arranca sin una.

Para que `make seed` cree la primera cuenta `admin` (D13), define `ADMIN_PASSWORD` en el
entorno; sin ella, no se siembra ninguna cuenta y el seed lo advierte.

## Migración desde el proyecto viejo

`agentes.db` se lleva al esquema nuevo con un migrador idempotente (reporte de reconciliación,
`--dry-run`, backup del origen y plan de rollback):

```sh
cd backend
uv run python -m scripts.migrate_from_sqlite --source ../../theythink-ai/agentes.db --dry-run
uv run python -m scripts.migrate_from_sqlite --source ../../theythink-ai/agentes.db \
    --admin-email admin@example.com
```

Detalle y vuelta atrás en [`docs/migration-rollback.md`](./docs/migration-rollback.md) y
ADR [`0023`](./docs/adr/0023-data-migration.md).

## Despliegue

Imagen de contenedor única (API + SPA en el mismo origen), migraciones como paso de release y
Postgres como única dependencia de infraestructura. Detalle en
[`docs/operations.md`](./docs/operations.md).

```sh
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
docker compose -f docker-compose.prod.yml up -d
```

## Estado

Fases 0–5 cerradas y los huecos de superficie de la propuesta §10 cerrados (2026-10-01).
La Fase 6 (endurecimiento y corte) está implementada (2026-10-02): imagen de producción,
límite de peticiones, política de contraseña y CSRF, backups con ensayo de restore, logging
estructurado y métrica de tokens inyectados. El ensayo de staging con el dump real ya está hecho
en local (migración idempotente, backup/restore y checklist §11 verificado). Queda desplegar en
el host real y, como **dependencia externa**, archivar `theythink-ai`: su repositorio es de otro
propietario y el equipo solo tiene permisos en `theyrethink-ai`
([runbook](./docs/runbook-cutover.md)). La Fase 7 es opcional.
El avance por fases está en [`DEVELOPMENT_PLAN.md`](./DEVELOPMENT_PLAN.md) §0.

