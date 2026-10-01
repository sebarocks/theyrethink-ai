# 0023 — Migración de datos desde `agentes.db` (Fase 5)

- **Estado:** aceptada
- **Fecha:** 2026-10-01
- **Fuente:** plan §5 (Fase 5); spike `S4`; propuesta §14 (D6, D7, D10, D13, D14)

## Contexto

La Fase 5 lleva el dump SQLite heredado (`agentes.db`) al esquema nuevo. El dump real es
mínimo —1 usuario, 8 agentes, 23 roles, 8 fuentes, 8 hilos vacíos, **0 conversaciones** y
ninguna memoria— pero el migrador debe ser general: puede haber despliegues con datos reales.
Restricciones que condicionan el diseño:

- Las conversaciones viven en el **checkpointer** y la memoria en el **`Store`**; escribir SQL
  propio para ellas está prohibido (AGENTS.md §3.3).
- `sesiones_chat` no tiene `user_id` (el modelo viejo no tenía usuarios finales), pero
  `threads.user_id` es `NOT NULL` (D6).
- La memoria vieja (`agentes.memoria`) era **por agente**, compartida por todos; la nueva es
  por `(agente, usuario)` (D1).
- Los hashes son `scrypt` de Werkzeug; el proyecto nuevo usa Argon2 y no quiere `werkzeug` en
  runtime.

## Decisión

### 1. Replay por la API pública (spike S4)

`AgentService.import_transcript()` reconstruye un transcript histórico con
`CompiledStateGraph.aupdate_state(..., as_node=START)`. Es **idempotente por rechazo**: si el
hilo ya tiene transcript, lanza `ValueError` en vez de duplicar. El migrador comprueba antes y
salta los hilos ya importados.

### 2. Los hilos nacen consolidados

Tras importar un transcript histórico, el migrador fija `last_consolidated_at` y
`last_consolidated_message_count` a la posición importada: la memoria de esos turnos ya viene
de `agentes.memoria` y no debe re-extraerse (ADR `0022`).

### 3. Hash heredado sin `werkzeug`

`app/security/passwords.py` verifica el formato `scrypt:N:r:p$salt$hex` con `hashlib.scrypt` y
`hmac.compare_digest` de la stdlib, y `needs_rehash()` lo marca. El login reescribe a Argon2 en
el primer acierto. Así no se agrega ninguna dependencia y el re-hash sigue siendo perezoso.

### 4. Propiedad de los hilos

`sesiones_chat` no tiene dueño: todas las sesiones migradas se asignan al **propietario**
(`--owner`; por defecto el único usuario, o el `admin`). Los agentes y las fuentes se hacen
*upsert* por clave natural (`name`/`key`).

### 5. Memoria compartida → fan-out

La memoria por agente se replica al namespace `(agente, usuario)` de **cada usuario migrado**:
era información compartida y nadie debe perderla. La dedup del núcleo evita repetir hechos.

### 6. Idempotencia y no intromisión

*Upsert* por clave natural y estas reglas explícitas:

- El `password_hash` de un usuario existente **no** se reescribe (pudo re-hashearse a Argon2).
- `last_consolidated_*` de un hilo existente **no** se toca.
- Las conversaciones solo se importan si el hilo no tiene transcript.

## Alternativas consideradas

- **Re-hash eager en la migración:** imposible sin la contraseña en claro.
- **Añadir `werkzeug` (runtime o extra):** una dependencia más para verificar 8 líneas de
  formato estable; se descarta.
- **Escribir el checkpointer con `aput`/SQL:** prohibido por AGENTS.md §3.3 y frágil ante
  subidas de versión de LangGraph.
- **Asignar la memoria solo al propietario:** pierde información si hay varios usuarios.
- **Preservar los ids de `sesiones_chat` como `threads.id`:** obliga a manipular secuencias y
  complica la idempotencia; se mapea viejo→nuevo en memoria.

## Consecuencias

- El migrador es re-ejecutable: una segunda corrida no crea filas ni duplica transcripts ni
  hechos (DoD de la Fase 5).
- Se documenta el límite de versión del replay (`langgraph 1.2.11`,
  `langgraph-checkpoint-postgres 3.1.2`) en `docs/spikes/S4-checkpointer-replay.md`.
- Rollback y recuperación ante fallo parcial en `docs/migration-rollback.md`.
- Sin endpoint de "olvidar memoria" en v1, el `Store` de un usuario migrado solo se puede
  limpiar con administración directa; queda como hueco conocido de la superficie de memoria.
