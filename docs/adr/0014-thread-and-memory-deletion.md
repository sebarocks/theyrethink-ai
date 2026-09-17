# 0014 — Borrar un hilo no borra la memoria

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §6.1, §14 (D10); plan §5 Fase 3

## Contexto
Un hilo y la memoria del usuario tienen alcances distintos: el hilo es una conversación concreta; la memoria son hechos sobre la persona, que sobreviven a esa conversación. Si ambas operaciones se mezclan, no hay forma de tener una sin la otra.

## Decisión
Borrar un hilo elimina el **checkpoint** y la fila de `threads`, y **no toca el `Store`**. "Olvidar memoria" es un endpoint aparte y explícito.

## Alternativas consideradas
- **Borrar la memoria junto con el hilo:** descartado; confundiría dos operaciones con semántica y alcance distintos a cambio de un borrado irreversible.
- **Un único endpoint de borrado total:** descartado por la misma razón: hay que poder eliminar una conversación sin perder lo que el agente recuerda.

## Consecuencias
- El usuario limpia su listado de hilos sin perder recuerdos, y olvidar la memoria es una acción deliberada y auditable.
- La UI de hilos expone dos acciones distintas (Fase 4); el borrado del checkpoint es irreversible.
- "Olvidar memoria" debe recorrer el namespace `("agent", agent_id, "user", user_id)` (ADR 0008).
