# Operaciones y despliegue

Runbook de producción de `theyrethink-ai` (Fase 6). Las decisiones están en
[ADR `0025`](./adr/0025-production-deployment.md) (despliegue), `0026` (límite de peticiones),
`0027` (sesión y contraseña) y `0028` (observabilidad).

---

## 1. Piezas y topología

| Pieza | Qué es | Estado durable |
|---|---|---|
| `api` | Imagen `Dockerfile` (FastAPI + SPA construida, mismo origen) | No |
| `postgres` | Datos de dominio, sesiones, cola de consolidación, checkpointer y `Store` | Volumen `pgdata` |
| Avatares | `AVATAR_STORAGE_DIR` | Volumen `avatars` |
| Backups | `pg_dump` a almacenamiento fuera del host de la base | Fuera del host |
| Proxy TLS | Termina HTTPS delante de `api` | — |

No hay Redis ni ningún otro servicio: la cola de consolidación vive en Postgres (D14).

## 2. Primer despliegue

1. **Configuración.** Copia `backend/.env.example` a `.env` **en la raíz del repo** (es el que
   leen Compose y la aplicación) y completa, como mínimo:
   `SECRET_KEY` (`openssl rand -hex 32`), `POSTGRES_PASSWORD`, `DATABASE_URL`,
   `ADMIN_EMAIL`/`ADMIN_PASSWORD` (primer administrador, D13) y `ENVIRONMENT=production`.
   `.env` no se versiona (AGENTS.md §5). Dentro de Compose, el host de la base es el **nombre del
   servicio**, no `localhost`: `DATABASE_URL=postgresql+asyncpg://theyrethink:<clave>@postgres:5432/theyrethink`.
2. **Construir la imagen.**
   ```sh
   docker compose -f docker-compose.prod.yml build
   ```
3. **Migrar (paso de release).** Antes de arrancar los workers, una sola vez:
   ```sh
   docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
   ```
   Este es el **orden canónico**: Alembic primero (dominio) y después el arranque de la
   aplicación, que completa las tablas de LangGraph con `setup()` idempotente en el `lifespan`
   (ADR `0016`, hueco 6 de la propuesta §4). La aplicación nunca migra al importar.
4. **Sembrar** el catálogo canónico y el administrador (solo la primera vez):
   ```sh
   docker compose -f docker-compose.prod.yml run --rm api python -m app.seed
   ```
5. **Arrancar.**
   ```sh
   docker compose -f docker-compose.prod.yml up -d
   ```
6. **Comprobar.**
   ```sh
   curl -fsS http://localhost:8000/healthz   # {"status":"ok"}
   curl -fsS http://localhost:8000/readyz    # {"status":"ok","database":"up"}
   ```

## 3. Actualizaciones

```sh
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
docker compose -f docker-compose.prod.yml up -d --build
```

Con `WEB_CONCURRENCY > 1` la actualización reinicia los workers de uno en uno solo si el
orquestador lo permite; con Compose hay una breve interrupción. La migración va **antes** del
reinicio. Si la migración no es compatible hacia atrás, la marcha atrás exige restaurar el
backup previo (ver §7).

## 4. Salud, señales y escala

- `/healthz` — *liveness*, no toca dependencias. Lo usa el `HEALTHCHECK` de la imagen.
- `/readyz` — *readiness*, toca Postgres. Es el que debe usar el balanceador.
- `SIGTERM` — `uvicorn` drena con `GRACEFUL_SHUTDOWN_SECONDS` (30 s por defecto) y el `lifespan`
  apaga el worker de consolidación.
- `WEB_CONCURRENCY` — número de workers (por defecto, `nproc`). Cada worker abre sus propias
  conexiones a Postgres: dimensiona el *pool* y `max_connections` antes de subirlo.
- El worker de consolidación corre en cada proceso; el *lease* de la cola (ADR `0022`) evita que
  dos workers procesen el mismo trabajo.
- **IP real detrás de proxy:** define `FORWARDED_ALLOW_IPS` con la IP del proxy para que
  `uvicorn` lea `X-Forwarded-For`. Sin proxy de confianza, déjalo vacío (la cabecera es
  falsificable y el límite por IP se podría eludir).

## 5. Observabilidad

- `LOG_FORMAT=json` en producción; los eventos de la aplicación llevan `request_id`, propagado
  desde `X-Request-Id` o generado (ADR `0028`). Los logs de acceso de `uvicorn` también son JSON,
  pero se emiten al terminar la respuesta y no llevan `request_id`; usa el `X-Request-Id` de la
  respuesta para enlazar una petición con sus eventos.
- `GET /metrics` (Prometheus) solo si `METRICS_ENABLED=true`; con `METRICS_TOKEN` exige
  `Authorization: Bearer`. Los contadores son **por proceso**: agrega por instancia en
  Prometheus, no esperes un único total.
- Métricas de D7 a vigilar: `memory_injected_tokens_last` frente a
  `memory_injection_budget_tokens` (techo = `0.4 × contexto`). Si se acercan de forma sostenida,
  toca abrir la compactación de memoria (Fase 7).

## 6. Backups

Procedimiento y ensayo de restore en [`docs/backup-restore.md`](./backup-restore.md). En corto:
`pg_dump` diario a almacenamiento externo, retención definida y **ensayo de restore**
verificado; el ensayo es requisito del DoD de la Fase 6.

## 7. Corte y vuelta atrás

En [`docs/runbook-cutover.md`](./runbook-cutover.md): checklist de corte, congelación de
`theythink-ai` y plan de rollback.
