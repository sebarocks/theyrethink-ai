# Runbook de corte y vuelta atrás

Cierre de la Fase 6: pasar a producción y archivar `theythink-ai` (propuesta §12, Fase 6;
[ADR `0025`](./adr/0025-production-deployment.md)). Este documento es el guion del día del
corte; los detalles de despliegue están en [`operations.md`](./operations.md) y los de copia en
[`backup-restore.md`](./backup-restore.md).

## 0. Precondiciones (gate de entrada)

- [ ] Fases 0–5 cerradas y suite verde (`pytest`, `ruff`, `lint-imports`, `deno check`,
      `deno test`, `test:unit`, `test:e2e`).
- [ ] **Migración de datos reales ensayada en staging**, con reporte de reconciliación sin
      discrepancias no explicadas (§Fase 5). El dump local está vacío: este paso es obligatorio.
- [ ] **Ensayo de restore exitoso** en staging con el backup del paso anterior.
- [ ] Check-list de la propuesta §11 verificado en el entorno de destino (autorización, sin
      secretos por defecto, subidas restringidas, límite de intentos, servidor sin `debug`).
- [ ] `SECRET_KEY`, `POSTGRES_PASSWORD` y `ADMIN_PASSWORD` propios del entorno, fuera del repo.
- [ ] Proxy TLS delante de `api`, `FORWARDED_ALLOW_IPS` configurado.
- [ ] Ventana de corte acordada y usuarios avisados.

## 1. Corte

1. **Congelar escrituras.** Anunciar la ventana y detener la escritura en el sistema antiguo
   (o ponerlo en modo lectura).
2. **Backup final del origen** y, si aplica, del destino antes de migrar.
3. **Migrar los datos incrementales** desde `theythink-ai` con el migrador (Fase 5):
   ```sh
   cd backend
   uv run python -m scripts.migrate_from_sqlite --source ../../theythink-ai/agentes.db \
       --admin-email <admin@dominio> --report /tmp/reconciliacion.txt
   ```
4. **Revisar el reporte** de reconciliación: sin discrepancias no explicadas.
5. **Migrar el esquema.** `docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head`.
6. **Arrancar** la API: `docker compose -f docker-compose.prod.yml up -d --build`.
7. **Smoke** (ver §3).

## 2. Vuelta atrás

| Escenario | Acción |
|---|---|
| La API nueva no arranca o falla en smoke | Volver la etiqueta de imagen anterior y reiniciar; el esquema no cambió si la migración no se aplicó |
| Una migración ya aplicada resulta incompatible | Restaurar el backup previo al corte en una base limpia (`restore_postgres.sh <dump> <base>`) y apuntar `DATABASE_URL` a ella |
| Datos migrados incorrectos | Repetir la migración es idempotente; si el daño es grave, restaurar el backup y rehacer el paso 3 |

Un `alembic downgrade` solo se usa si está probado; por defecto, la vuelta atrás es **restaurar
el backup**, no deshacer migraciones hacia atrás.

## 3. Smoke de corte

```sh
curl -fsS https://<dominio>/healthz
curl -fsS https://<dominio>/readyz
```

Después, en el navegador:

- login con la cuenta de administrador y una cuenta normal,
- abrir un chat, enviar un mensaje y recibir streaming,
- comprobar que el panel de memoria muestra hechos y que «olvidar» funciona,
- abrir el dashboard de admin y la vista de transcripciones,
- probar las tres skins (web, WhatsApp, Telegram).

Smoke de carga mínimo: `backend/scripts/smoke_load.py` (ver §4).

## 4. Carga mínima

```sh
cd backend
uv run python -m scripts.smoke_load --base-url https://<dominio> --requests 50 --concurrency 5
```

Mide latencia de `/healthz` y `/readyz` y el código de estado bajo concurrencia. No sustituye a
una prueba de carga real: es una comprobación de que el servidor con `WEB_CONCURRENCY` no se
cae ni devuelve 5xx con tráfico moderado.

## 5. Archivo de `theythink-ai`

**Dependencia externa.** El repositorio es de `bemtorres/theythink-ai` y el equipo solo tiene
permisos en `theyrethink-ai`, así que estos pasos los ejecuta **el propietario del repo
antiguo** (además, `AGENTS.md` §1/§8 prohíbe que un agente lo modifique). Mientras no se haga,
`theythink-ai` sigue siendo la referencia de solo lectura.

```sh
# 1. Etiqueta del estado final, para poder consultarlo siempre.
git -C <clon-de-theythink-ai> tag -a archive/pre-rewrite -m "Estado final antes del corte a theyrethink-ai"
git -C <clon-de-theythink-ai> push origin archive/pre-rewrite

# 2. Archivar en el remoto (GitHub: Settings -> Archive this repository) y dejar el README
#    apuntando al proyecto nuevo.

# 3. Detener y deshabilitar el servicio del sistema antiguo.
```

- [ ] Tag creado y publicado.
- [ ] Repositorio archivado / solo lectura.
- [ ] README del proyecto antiguo apunta a `theyrethink-ai`.
- [ ] `docker-compose` o servicio del sistema antiguo detenido y deshabilitado.

## 6. Cierre

- [ ] Actualizar el registro de estado en `DEVELOPMENT_PLAN.md` §0 (Fase 6 cerrada).
- [ ] Confirmar que los backups diarios del proyecto nuevo están corriendo.
- [ ] Vigilar `memory_injected_tokens_last` frente a `memory_injection_budget_tokens` durante las
      primeras semanas (ADR `0028`): si se acercan, abrir la Fase 7.

> **Ensayo local ya realizado (2026-10-04).** Sobre una base limpia con el dump real
> (`agentes.db`): migración dry-run + real + segunda corrida idempotente, backup/restore con
> conteos idénticos y checklist §11 verificado con `curl` contra la API apuntando a esa base.
> Falta repetirlo en el host de destino, que es donde entran TLS, proxy y usuarios reales.
