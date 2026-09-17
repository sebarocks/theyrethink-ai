# S2 — Checkpointer y Store de LangGraph sobre Postgres, y su relación con Alembic

- **Fecha:** 2026-09-16
- **Estado:** ✅ concluido (ejecutado contra `postgres:17-alpine` real)
- **Bloquea:** Fases 1 y 2
- **Ámbito:** `/tmp` y un script temporal ya eliminado; el Postgres es el de `docker-compose.yml`

## Pregunta

¿El `AsyncPostgresSaver` y el `AsyncPostgresStore` funcionan sobre el Postgres del proyecto,
son idempotentes, y cómo conviven con Alembic (que también es autoridad de migración sobre
la misma base)?

## Lo que se ejecutó

Un sondeo temporal que: listó las tablas, intentó `setup()` dos veces, hizo un *roundtrip*
de `aput`/`aget` en el `Store`, compiló un grafo mínimo con `checkpointer` + `store`, invocó
una vez, leyó el estado persistido y borró el hilo.

## Resultados

| Comprobación | Resultado |
|---|---|
| `AsyncPostgresSaver.setup()` | OK |
| `setup()` invocado dos veces | OK — **idempotente** |
| `AsyncPostgresStore.setup()` | OK |
| `store.aput` / `store.aget` | OK — *roundtrip* correcto |
| Grafo con `checkpointer` + `store` | OK — 2 mensajes persistidos y recuperados |
| `saver.adelete_thread()` | OK — el hilo queda vacío tras borrarlo |
| Tablas creadas | `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`, `store`, `store_migrations` |

## Hallazgo 1 — Las etiquetas del namespace deben ser `str`

```
InvalidNamespaceError: Invalid namespace label '1' found in ('agent', 1, 'user', 1).
Namespace labels must be strings, but got int.
```

El namespace de memoria del proyecto, **tal como estaba escrito en la propuesta**
(`("agent", agent_id, "user", user_id)`), falla en runtime porque `agent_id` y `user_id` son
enteros. Hay que castear: `("agent", str(agent_id), "user", str(user_id))`.

**Acción:** corregido en la propuesta §5.3/§14, en `AGENTS.md` §4 y aquí. Es un error que
habría aparecido en la Fase 2, con el coste de depuración de un grafo; detectarlo ahora es
justamente el valor del spike.

## Hallazgo 2 — Alembic necesita excluir seis tablas

`setup()` crea las tablas en el esquema `public`, así que **el autogenerate de Alembic las
verá** y propondrá migraciones para ellas (o peor, un `downgrade` podría borrarlas). Este era
el *gap 6* del plan, ahora con los nombres exactos:

```
checkpoints, checkpoint_blobs, checkpoint_writes, checkpoint_migrations, store, store_migrations
```

**Acción para la Fase 1:** configurar `include_object`/`include_name` en `env.py` de Alembic
para excluirlas del autogenerate, y documentar el orden (primero `setup()` de la librería,
después las migraciones de dominio).

## Consecuencias para la implementación

- El `lifespan` de Fase 2 debe llamar a `setup()` de ambos objetos; es seguro hacerlo en cada
  arranque gracias a la idempotencia.
- `checkpoint_migrations` y `store_migrations` son las marcas de versión **de la librería**:
  no son nuestras y no se tocan.
- El `Store` soporta borrado por hilo sin afectar al resto, lo que respalda D10 (borrar un
  hilo no toca la memoria).

## Pendiente

Nada crítico. En Fase 2 conviene medir el coste de `aget_state` con historiales largos para
dimensionar `threads.message_count` y `last_preview`.