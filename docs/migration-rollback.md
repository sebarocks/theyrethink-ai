# Plan de rollback de la migración (Fase 5)

El migrador `scripts/migrate_from_sqlite.py` **solo agrega o actualiza** filas de dominio
(`roles`, `knowledge_sources`, `agents`, `agent_sources`, `users`, `threads`) y escribe
conversaciones en el checkpointer y hechos en el `Store`. Nunca borra datos de usuario. Aun
así, toda migración necesita una vuelta atrás ensayada.

## Antes de migrar

1. **Respaldo del origen** (lo hace el migrador automáticamente salvo `--no-backup`):
   `agentes.db.bak-<UTC>` junto al original. El origen se abre en modo solo lectura; este
   respaldo protege ante un error humano.
2. **Respaldo del destino** (manual, obligatorio en staging/producción):

   ```sh
   pg_dump --format=custom --file=theyrethink-pre-migration.dump "$DATABASE_URL"
   ```

3. **Ensayo en seco**: `--dry-run` sobre una copia de la base destino. Reporta conteos,
   huérfanos, descartes y colisiones sin escribir.

## Vuelta atrás

### Opción A — rollback total (recomendada)

Restaura el destino al estado previo; el checkpointer y el `Store` vuelven con él.

```sh
pg_restore --clean --if-exists --dbname "$DATABASE_URL" theyrethink-pre-migration.dump
```

### Opción B — rollback por datos (sin dump)

Como el migrador es idempotente y no borra, se puede deshacer por clave natural:

- `threads` migrados: borrarlos con la semántica de D10 (checkpoint + fila, **no** toca el
  `Store`), es decir `DELETE` vía `AgentService.delete_thread` o el endpoint de la API.
- `agent_sources` / `agents` / `knowledge_sources` / `roles`: borrar solo las filas que no
  existían antes (comparar con el reporte `*_creados`).
- `users`: borrar solo los usuarios `*_creados`; un usuario existente no se modificó salvo el
  correo sintetizado del propietario cuando estaba en `@migrated.invalid`.
- **La memoria del `Store` no se borra con el hilo.** Si hace falta, se elimina por namespace
  `("agent", <agent_id>, "user", <user_id>)` con una herramienta de administración; no hay
  endpoint de olvido en v1 (hueco conocido, ver revisión previa a Fase 5).

### Entornos de desarrollo

```sh
docker compose down -v            # borra el volumen de Postgres
docker compose up -d postgres
cd backend && uv run alembic upgrade head && uv run python -m app.seed
```

## Recuperación ante fallo a mitad de migración

El migrador no es transaccional de punta a punta (dominio, luego checkpointer/`Store`):

- Si falla en la fase de dominio, la transacción no se confirma y no queda nada a medias.
- Si falla importando conversaciones, los transcripts ya importados quedan; **volver a
  ejecutar** salta los que ya están (`transcripts_ya_presentes`) y continúa. No duplica.
- Si falla escribiendo memoria, la dedup por contenido hace que reintentar no duplique hechos.

## Verificación posterior

1. `uv run python -m scripts.migrate_from_sqlite --source <db> --dry-run` sobre el destino
   migrado: debe reportar 0 creaciones.
2. Conteos: `usuarios`, `roles`, `agentes`, `fuentes`, `hilos` y `mensajes` del reporte deben
   coincidir con el origen (salvo descartes reportados).
3. Fidelidad de un hilo de muestra: `GET /api/v1/threads/{id}/messages`.
4. `/healthz` y `/readyz` en verde.
