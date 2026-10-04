# 0028 — Observabilidad de producción: logs JSON, tokens inyectados y `/metrics`

- **Estado:** aceptada
- **Fecha:** 2026-10-02
- **Fuente:** propuesta §13 y §14 (D25, D7); `DEVELOPMENT_PLAN.md` §7

## Contexto

La observabilidad se adelantó a la Fase 2 porque depurar un grafo sin logs correlacionados es
caro (§4, hueco 7). Lo que existe hoy es `app/agent/observability.py`: un `log_event()` que emite
un nombre de evento y campos (`thread_id`, `agent_id`, `user_id`). No hay formateador, ni
`request_id`, ni métricas.

El plan §7 exige además una métrica concreta de D7: **tokens de memoria inyectados por turno
frente al techo de `0.4 × contexto`**, y una tasa de acierto de caché del prefijo
`[system][historial]`. Sin esa métrica, la decisión de compactar memoria (Fase 7) se tomaría a
ojo.

## Decisión

1. **Logging estructurado.** `LOG_FORMAT=json` en producción y `text` en desarrollo. El
   formateador JSON serializa el mensaje, el nivel, el logger y los campos de `extra`
   (`event`, ids, `request_id`). No cambia la firma de `log_event`.
2. **Correlación por `request_id`.** Un middleware lee `X-Request-Id` (o genera uno), lo pone en
   el `contextvar` que el formateador consulta y lo devuelve en la respuesta. Los eventos del
   núcleo lo heredan sin pasarlo por parámetro. Los logs de **acceso** de `uvicorn` también van
   en JSON, pero se emiten después de terminar la respuesta y por eso no llevan `request_id`
   (sí el cliente, la ruta y el estado); el `X-Request-Id` de la respuesta es el que enlaza una
   petición concreta con sus eventos.
3. **Métrica de D7.** En el nodo `respond`, tras seleccionar los hechos inyectables, se registra:
   - `chat_turns_total` (contador),
   - `memory_injected_tokens` (suma histórica) y `memory_injected_tokens_last` (último turno),
   - `memory_injection_budget_tokens` (techo vigente, `0.4 × contexto`),
   - `memory_facts_injected` (suma de hechos inyectados).
4. **Caché del proveedor (*best-effort*).** Cuando la respuesta trae `usage_metadata` con
   `input_token_details.cache_read`, se acumula en `prompt_cache_read_tokens`. No todos los
   proveedores OpenAI-compatibles lo publican, así que la ausencia de dato no es un error.
5. **Exposición.** `GET /metrics` en formato Prometheus. Solo se sirve si
   `METRICS_ENABLED=true` (por defecto **desactivado**); si `METRICS_TOKEN` está definido, exige
   `Authorization: Bearer <token>`. Es un endpoint de operación: no se enlaza desde la SPA.

El registro de métricas vive en `app/metrics.py`, fuera de `app/agent/`, porque lo alimenta el
núcleo y lo expone la API. Se añade a `source_modules` del contrato de import-linter.

## Alternativas consideradas

- **`prometheus-client`.** Formato y *buckets* listos, pero una dependencia más para cinco
  contadores; el texto de Prometheus es trivial de emitir a mano y así el núcleo sigue sin
  depender de nada de observabilidad. Descartada de momento.
- **`structlog`.** Cómodo, pero sustituye el logging estándar y obliga a migrar todas las
  llamadas; `logging` + formateador JSON cubre el requisito. Descartada.
- **OpenTelemetry / LangSmith.** Valioso para trazas de LLM, pero es una plataforma externa con
  coste y configuración; la propuesta ya lo marca como opcional. Se deja para Fase 7.
- **`/metrics` abierto por defecto.** Cómodo para el *scrape* local, pero expone uso y coste;
  por defecto cerrado y se activa explícitamente.

## Consecuencias

- Con varios workers (D22) los contadores son **por proceso** y Prometheus debe sumar por
  instancia; el endpoint no agrega entre workers. Se documenta en el runbook.
- La métrica de tokens inyectados permite decidir con datos si la compactación de memoria (Fase
  7) es necesaria, en vez de por intuición.
- El `request_id` facilita seguir un turno completo (API → grafo → consolidación) en los logs.
