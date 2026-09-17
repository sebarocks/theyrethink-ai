# 0005 — Persistencia del agente por checkpointer y Store de LangGraph

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §3 (A4, A5), §5.2, §6.2; plan §5 Fase 2

## Contexto
El proyecto actual mantiene a mano el esquema de sesiones, mensajes y memoria (`conversaciones`, `sesiones_chat`, `agentes.memoria`), y ahí está el grueso del código de mantenimiento que el rewrite quiere eliminar.

## Decisión
Adoptar **LangGraph desde el inicio**: la conversación la persiste el **checkpointer** y los hechos de memoria el **`Store`** (`langgraph-checkpoint-postgres`: `AsyncPostgresSaver`, `AsyncPostgresStore`). **No se escribe esquema propio** de conversación ni de memoria.

## Alternativas consideradas
- **LangChain a secas o un grafo manual:** descartado; el checkpointer + Store son el ahorro real de código.
- **Esquema propio de conversaciones/mensajes:** descartado; implicaba tablas y consultas manuales de historial.

## Consecuencias
- Prohibido crear tablas de mensajes, sesiones o memoria propias (AGENTS.md §3.3).
- `threads` queda como cache de UI: si discrepa del checkpointer, manda el checkpointer.
- Las tablas de la librería se crean con `saver.setup()` / `store.setup()` en el `lifespan`; el grafo de memoria **no** usa checkpointer, porque no es una conversación.
- Ambas capas comparten la misma BD y el mismo pool async.
- Cuesta heredar el ritmo de versiones de la librería; se mitiga fijando versiones exactas y encerrándola tras `agent/` (§13).
