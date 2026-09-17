# 0012 — Streaming por SSE

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §5.5, §8, §14 (D5); plan §2 (S3), §5 Fase 3

## Contexto
El chat necesita emitir tokens conforme el modelo los produce, y el transporte se decide una vez porque condiciona el contrato del endpoint y el cliente.

## Decisión
**SSE** para el stream de tokens en `/api/v1/threads/{id}/messages`, decidido para v1.

## Alternativas consideradas
- **WebSocket:** descartado mientras no aparezca necesidad real bidireccional.

## Consecuencias
- El endpoint declara un formato de evento estable, con heartbeat y cancelación (Fase 3).
- La consolidación de memoria no va en el camino del stream: se encola al cerrar el turno (D7/D14, ADR 0013). Hoy esa segunda llamada bloqueaba la respuesta.
- El cliente generado (`openapi-fetch`) debe soportar streaming con cookies `SameSite` (spike S3).
- Cuesta: SSE es unidireccional; si surge una necesidad bidireccional real, esta decisión se revisa.
