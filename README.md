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

## Toolchain

- **Python:** `uv` (Astral). Prohibido `pip` y `requirements.txt`; el pin vive en `uv.lock`.
- **Frontend:** Deno. Prohibido Node y npm.

Detalle y comandos en [`AGENTS.md`](./AGENTS.md).

## Arranque rápido

```sh
make db      # levanta Postgres con docker compose
make migrate # aplica migraciones (Fase 1)
make seed    # siembra los datos canónicos (Fase 1)
make dev     # levanta la API en modo desarrollo
```

API en `http://localhost:8000` · `/healthz` · `/readyz` · `/docs`.

Antes de ejecutar, copia `backend/.env.example` a `backend/.env` y **genera una
`SECRET_KEY` propia** (`openssl rand -hex 32`). No hay valor por defecto: la aplicación no
arranca sin una.

## Estado

Fase 0 (andamiaje) en curso. El avance por fases está en
[`DEVELOPMENT_PLAN.md`](./DEVELOPMENT_PLAN.md) §0.