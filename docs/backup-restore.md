# Backups y restore

Procedimiento de copia y ensayo de recuperación (Fase 6, [ADR `0025`](./adr/0025-production-deployment.md)).
El DoD de la Fase 6 exige **ensayo de restore exitoso**, no solo que exista el backup.

## Qué se respalda

Un `pg_dump` en formato *custom* de la base completa. Cubre las tres cosas que viven en
Postgres:

- **dominio** (agentes, roles, fuentes, hilos, usuarios, sesiones),
- **cola de consolidación** (`consolidation_jobs`),
- **checkpointer y `Store` de LangGraph** (`checkpoints*`, `store`).

Los **avatares** (ADR `0017`) no están en la base: se respaldan aparte, copiando el volumen
`avatars` (`AVATAR_STORAGE_DIR`).

## Scripts

| Acción | Comando |
|---|---|
| Backup | `./backend/scripts/backup_postgres.sh` |
| Restore a base aislada | `./backend/scripts/restore_postgres.sh <dump>` |
| Restore a base concreta | `./backend/scripts/restore_postgres.sh <dump> <base>` |

Variables útiles: `COMPOSE_FILE` (por defecto `docker-compose.prod.yml`), `BACKUP_DATABASE`
(por defecto la base del contenedor; sirve para respaldar staging), `BACKUP_DIR`
(por defecto `backups/`), `BACKUP_RETENTION_DAYS` (por defecto 14 días; `0` desactiva la purga).

`pg_dump`/`pg_restore` corren **dentro del contenedor de Postgres**, así que no hace falta
cliente en el host.

## Frecuencia y retención

- **Diario** en horario de baja actividad; en un volumen de este tamaño el dump es de segundos.
- Retención mínima acordada: 14 días en caliente. Una copia semanal debe salir **fuera del host
  de la base**: un backup en el mismo disco que la base no es un backup.
- Antes de cada actualización con migración: backup manual etiquetado, para poder volver atrás.

## Ensayo de restore (obligatorio)

El restore siempre se ensaya sobre una **base destino aislada** (`theyrethink_restore`), nunca
sobre la de producción:

```sh
COMPOSE_FILE=docker-compose.yml ./backend/scripts/backup_postgres.sh
COMPOSE_FILE=docker-compose.yml ./backend/scripts/restore_postgres.sh backups/<dump>
```

Verificación de paridad (debe cuadrar en todas las filas):

```sql
-- en theyrethink (origen)
SELECT 'agents='||count(*) FROM agents UNION ALL
SELECT 'roles='||count(*) FROM roles UNION ALL
SELECT 'knowledge_sources='||count(*) FROM knowledge_sources UNION ALL
SELECT 'agent_sources='||count(*) FROM agent_sources UNION ALL
SELECT 'threads='||count(*) FROM threads;

-- en theyrethink_restore (destino): mismos números
```

Además, comprobar que están las tablas de la librería:

```sql
SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';
SELECT count(*) FROM checkpoints;
SELECT count(*) FROM store;
```

Cuando termina el ensayo, la base de prueba se puede borrar:

```sh
docker compose exec postgres dropdb --if-exists -U theyrethink theyrethink_restore
```

### Ensayo registrado

| Fecha | Backup | Origen → destino | Resultado |
|---|---|---|---|
| 2026-10-02 | `theyrethink-20261002T192043Z.dump` (74,8 KB) | `theyrethink` → `theyrethink_restore` | ✅ 16/16 tablas; `agents=19`, `roles=23`, `sources=19`, `agent_sources=19`, `threads=2`, `checkpoints=24`, `store=2` idénticos |
| 2026-10-04 | `theyrethink-20261004T184227Z.dump` (57,5 KB) | `theyrethink_staging` (dump real migrado) → `theyrethink_staging_restore` | ✅ `agents=8`, `roles=23`, `knowledge_sources=8`, `agent_sources=8`, `threads=8`, `users=1` idénticos |

El ensayo se hizo con el `docker-compose.yml` de desarrollo (misma imagen de Postgres que
producción), que es suficiente para validar el procedimiento; el ensayo definitivo se repite en
el host de destino antes del corte.

## Recuperación de avatares

```sh
# copia del volumen (producción)
docker run --rm -v theyrethink-ai-prod_avatars:/data -v "$PWD/backups:/backup" alpine \
    tar czf /backup/avatars-$(date -u +%Y%m%dT%H%M%SZ).tar.gz -C /data .
```

Restaurar es el proceso inverso sobre el volumen vacío. Los avatares perdidos no rompen la
conversación: la UI los muestra como ausentes.
