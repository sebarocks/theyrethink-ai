# 0025 — Despliegue de producción: imagen única y migraciones como paso de release

- **Estado:** aceptada
- **Fecha:** 2026-10-02
- **Fuente:** propuesta §14 (D22, D4, D8, D11, D13, D14); ADR `0011`, `0016`, `0017`, `0018`, `0022`

## Contexto

Hasta la Fase 5 el único artefacto de infraestructura era `docker-compose.yml`, y solo para
Postgres en desarrollo. El backend se ejecutaba con `uvicorn --reload` y la SPA se servía desde
el build local. Faltaba todo lo que hace falta para producción: cómo se empaqueta, con cuántos
procesos se sirve, en qué orden se aplican las migraciones y qué estado es durable.

Restricciones ya decididas que condicionan la solución:

- **Mismo origen (D4):** FastAPI sirve la SPA construida; no hay CORS ni un segundo servidor web.
- **SPA estática (D8, ADR `0018`):** `adapter-static` deja a Deno **solo en tiempo de build**; el
  runtime no necesita Node ni Deno.
- **Dos autoridades de migración (hueco 6 de §4):** Alembic para el dominio y `setup()` de
  LangGraph para sus tablas, idempotente, en el `lifespan` (ADR `0016`).
- **Cola en Postgres con *lease* (D14, ADR `0022`):** varios workers pueden competir por la
  consolidación sin duplicar trabajo.
- **Avatares en volumen local (D12, ADR `0017`):** el sistema de archivos del contenedor no es
  durable por sí solo.

## Decisión

1. **Imagen de contenedor única, multi-etapa, en la raíz del repo.** El *builder* construye la
   SPA con Deno (`deno task build`) e instala las dependencias Python con `uv sync --locked`; la
   imagen final es `python:3.13-slim` con el backend, sus dependencias y `frontend/build`. No
   lleva Node, npm ni Deno.
2. **`uvicorn` con `WEB_CONCURRENCY` workers** (por defecto el número de CPUs). `debug` queda
   apagado siempre (ya lo fuerza `Settings` en producción) y el apagado es ordenado ante
   `SIGTERM`. El worker de consolidación corre dentro de cada proceso y el *lease* de ADR `0022`
   evita que N procesos procesen el mismo trabajo.
3. **Migraciones como paso de release.** `alembic upgrade head` se ejecuta en un contenedor de
   un solo uso **antes** de arrancar o actualizar los workers. La aplicación nunca migra al
   importar. Después, el `setup()` idempotente de LangGraph completa lo suyo en el `lifespan`.
4. **Salud y señales.** `/healthz` es *liveness* (no toca dependencias); `/readyz` toca Postgres
   y es lo que debe usar el balanceador para enrutar. El `HEALTHCHECK` de la imagen usa
   `/healthz`.
5. **Volúmenes para todo lo durable:** datos de Postgres, `AVATAR_STORAGE_DIR` y los *backups*.
   El contenedor de la API no guarda estado que importe.
6. **Configuración solo por variables de entorno**, con `SECRET_KEY` obligatoria y sin valor por
   defecto (AGENTS.md §5).

El `docker-compose.prod.yml` materializa el escenario de un solo host; el `Dockerfile` es
reutilizable por cualquier orquestador.

## Alternativas consideradas

- **`systemd` + `uv` sobre el host.** Menos reproducible y ata el despliegue a la máquina;
  además obliga a gestionar el build de la SPA por separado. Descartada.
- **Kubernetes.** Sobredimensionado para el volumen real (un host, Postgres y una API).
  Descartada.
- **Servir la SPA con Caddy/nginx y la API aparte.** Reintroduce dos orígenes, cookies
  *cross-site* y una pieza más que operar; D4 ya eligió el mismo origen. Descartada.
- **Migrar en el arranque de los workers.** Con varios workers hay carrera y un fallo de
  migración deja procesos a medias. Descartada.

## Consecuencias

- El despliegue es reproducible y el runtime no arrastra Node (coherente con `AGENTS.md` §2).
- Con `WEB_CONCURRENCY > 1` aumentan las conexiones a Postgres: hay que dimensionar el *pool* y
  los límites de Postgres, no solo la CPU.
- Actualizar la aplicación exige un paso explícito de migración; un *rollback* de imagen sin
  migración inversa puede ser incompatible, así que el runbook documenta el orden y el plan de
  vuelta atrás.
- Los *backups*, el ensayo de restore y el corte quedan en `docs/operations.md`.
