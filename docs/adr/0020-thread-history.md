# 0020 — Lectura del historial de un hilo

- **Estado:** aceptada
- **Fecha:** 2026-09-23
- **Fuente:** propuesta §5.5, §8, §14 (D16); plan §3, §5 Fase 4

## Contexto

La UI necesita reanudar un hilo (mostrar la conversación previa) y el dashboard, las
transcripciones. El contrato de la Fase 3 solo exponía `POST /api/v1/threads/{id}/messages`
(SSE): no había forma de **leer** el transcript.

## Decisión

`GET /api/v1/threads/{id}/messages` devuelve el transcript del hilo leyéndolo del
**checkpointer** a través de `agent/service.py` (DTOs de dominio). Solo se exponen los
mensajes `user`/`assistant`.

## Alternativas consideradas

- **Tabla propia de mensajes:** descartada; viola `AGENTS.md` §3.3 (cero SQL propio para
  conversación) y reintroduce el esquema que el rewrite elimina.
- **Leer el checkpointer desde el router:** descartada; rompe la costura única
  (`AGENTS.md` §3.1/§3.2).

## Consecuencias

- El transcript es el del checkpointer: si `threads` (cache de UI) discrepa, manda el
  checkpointer (`AGENTS.md` §3.4).
- El `system_prompt` y la memoria inyectada **no** se exponen: no son conversación (D7).
- Cambia el contrato OpenAPI: hay que actualizar el snapshot y regenerar el cliente.
- Autorización: pertenencia del hilo (404 si no es del usuario), como el resto de `threads`.
