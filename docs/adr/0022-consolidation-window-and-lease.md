# 0022 — Ventana y lease de la consolidación de memoria

- **Estado:** aceptada
- **Fecha:** 2026-10-01
- **Fuente:** propuesta §14 (D7, D14); ADR `0013`; corrección previa a la Fase 5

## Contexto

La ADR `0013` fijó la cola en Postgres con `SKIP LOCKED` y la marca de agua
`threads.last_consolidated_at`. Al revisar la implementación antes de la Fase 5 aparecieron
tres fallos que la ADR no cubría:

1. **Pérdida de turnos.** `consolidate()` extraía solo el *último* turno, pero avanzaba la
   marca de agua a `job.created_at`. Si la cola se atrasaba (o un trabajo se reintentaba tras
   un turno nuevo), los turnos intermedios nunca se extraían: hechos perdidos en silencio.
   La marca temporal no puede delimitar la ventana porque los mensajes del checkpointer no
   tienen timestamp accesible.
2. **Doble reclamo.** `claim()` documentaba «excluyendo los ya reclamados» pero no filtraba
   por `claimed_at`: con dos workers (o tras un crash) el mismo trabajo se procesaba dos
   veces. La deduplicación evitaba hechos duplicados, no el costo 2×.
3. **Worker mortal.** `run_forever()` no protegía `run_once()`: un error transitorio al
   reclamar (base caída) mataba la tarea de fondo sin log, y la consolidación se detenía
   hasta el siguiente reinicio.

## Decisión

- **Ventana por posición.** `threads.last_consolidated_message_count` guarda cuántos mensajes
  del transcript ya se consolidaron. `consolidate()` extrae **todos** los turnos desde esa
  posición hasta el final, y avanza el marcador al total (con `max()`, para no retroceder).
  `last_consolidated_at` se conserva como marca de agua para descartar reintentos del mismo
  trabajo. Un trabajo que llega cuando ya no hay ventana pendiente se marca y termina sin
  llamar al LLM. La migración `0004` añade la columna.
- **Lease en el reclamo.** `claim()` solo toma trabajos con `claimed_at IS NULL` o con el
  lease vencido (`consolidation_lease_seconds`, por defecto 300 s). Un worker caído libera su
  trabajo solo.
- **Worker tolerante a fallos.** `run_forever()` envuelve `run_once()` en `try/except`, lo
  registra y reintenta en el siguiente intervalo.

La columna es un **marcador de posición**, no contenido de conversación: no crea una tabla de
mensajes ni duplica el historial (AGENTS.md §3.3). El transcript sigue viviendo en el
checkpointer y `threads` sigue siendo caché de UI.

## Alternativas consideradas

- **Guardar el texto del turno en la cola.** Haría cada trabajo autocontenido, pero escribe
  conversación en SQL propio y rompe AGENTS.md §3.3. Descartada.
- **Delimitar por `last_consolidated_at` y timestamps de mensaje.** El checkpointer no expone
  un timestamp por mensaje. Descartada.
- **Lease con tabla de *locks* aparte.** Más superficie para el mismo efecto; `claimed_at` ya
  existía sin usarse.

## Consecuencias

- Ningún turno queda sin extraer aunque la cola acumule trabajos; a cambio, cada consolidación
  procesa todos los turnos pendientes (más contexto en una sola llamada al extractor).
- Con varios workers, el trabajo no se duplica mientras el lease esté vigente; si un worker
  muere a mitad, el trabajo se reintenta al vencer el lease (idempotente por los marcadores).
- `consolidation_lease_seconds` debe ser mayor que la extracción más lenta esperada.
- El `DoD` de la Fase 2 se re-verifica con `test_service.py` (ventana con dos turnos
  pendientes), `test_consolidation.py` (lease y worker resiliente) y `test_api_chat.py`.
