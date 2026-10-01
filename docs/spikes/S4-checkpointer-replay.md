# S4 — Replay del checkpointer por la API pública

- **Fecha:** 2026-10-01
- **Estado:** ✅ concluido (`backend/scripts/spike_s4.py`, reproducible sin red ni base)
- **Bloquea:** Fase 5 (migración de datos)
- **Ámbito:** `backend/app/agent/service.py`, `backend/scripts/spike_s4.py`

## Pregunta

¿Se puede reconstruir una conversación histórica en el checkpointer usando **solo la API
pública** del grafo y leerla después por `agent/service.py`, sin escribir filas a mano ni
acoplarse al formato interno de `langgraph-checkpoint`?

## Lo que se ejecutó

`uv run python -m scripts.spike_s4`, con `InMemorySaver` + `InMemoryStore` y un LLM falso que
revienta si se invoca (el replay **no** llama al modelo). Recorre la misma ruta que usará el
migrador, `AgentService.import_transcript()`:

1. Escribe el transcript con `CompiledStateGraph.aupdate_state(config, {"messages": [...]},
   as_node=START)` — API pública, sin SQL ni tablas propias.
2. Lo lee con `read_messages()` y compara rol/texto mensaje a mensaje.
3. Comprueba que el estado persistido no queda con `system_prompt` ni memoria.
4. Comprueba el aislamiento por `thread_id`.
5. Reimporta el mismo hilo para ver qué pasa.

## Resultados

```
langgraph = 1.2.11
langgraph-checkpoint-postgres = 3.1.2

[A] aupdate_state (API publica) ..... OK
[B] read_messages round-trip fiel .. OK   (4 mensajes)
[C] sin system_prompt persistido .... OK
[D] aislamiento por thread_id ...... OK
[E] reimportar se rechaza ........... OK

Resultado: CUMPLE
```

## Hallazgos

1. **`as_node` no es opcional en la práctica.** En un hilo vacío LangGraph infiere el nodo,
   pero un segundo `aupdate_state` sobre el mismo hilo falla con
   `InvalidUpdateError: Ambiguous update, specify as_node`. La importación fija
   `as_node=START`: el transcript es el estado *de entrada*, anterior a cualquier turno.
2. **El reducer `add_messages` agrega.** Si se importara dos veces, la historia se
   duplicaría en silencio. Por eso `import_transcript()` es **idempotente por rechazo**:
   si el hilo ya tiene transcript, lanza `ValueError` en vez de duplicar. El migrador
   comprueba antes y salta los hilos ya importados.
3. **El replay no ensucia el prompt.** El `system_prompt` se resuelve en `load_context` al
   primer turno real, no al importar; la memoria se inyecta de forma transitoria (D7). El
   estado importado es exactamente `[user][assistant]…`.

## Límite de versión

El spike se cierra contra **`langgraph 1.2.11`** y **`langgraph-checkpoint-postgres 3.1.2`**.
`aupdate_state`/`aget_state` son API pública estable, pero el comportamiento de inferencia de
`as_node` es el que obligó a fijarlo explícitamente; al subir de versión menor conviene
re-ejecutar este spike (30 s, sin dependencias externas).

## Consecuencias para la Fase 5

- El migrador importa conversaciones con `import_transcript()` y **no** escribe filas del
  checkpointer ni del `Store` (AGENTS.md §3.3).
- Al importar un transcript histórico, el migrador marca el hilo como ya consolidado
  (`last_consolidated_at` y `last_consolidated_message_count` a la posición importada): la
  memoria de esos turnos ya viene de `agentes.memoria` y no debe re-extraerse.
- La fidelidad se verifica con un test que compara el transcript reconstruido con el de
  origen sobre fixtures sintéticas.
