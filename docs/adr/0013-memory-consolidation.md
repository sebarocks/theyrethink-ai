# 0013 — Consolidación de memoria y orden del prompt

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §5.3, §13, §14 (D7, D14); plan §4 (huecos 5, 10, 11, 12)

## Contexto
La extracción de memoria de cada turno bloqueaba la respuesta (`app.py:976`), y `BackgroundTask` es *best-effort*: se pierde con reinicios y se duplica con varios workers. Además, la caché de prompt se cobra por prefijo idéntico, y un *cache miss* cuesta del orden de 10× un *cache hit*.

## Decisión
- **Disparador `N=1`:** se consolida en cada turno, asumiendo el costo 2×. `N` es palanca de configuración, no lógica adaptativa.
- **Inyección sin selección:** todos los hechos del namespace, con techo `0.4 × contexto_del_modelo` calculado en runtime, nunca hardcodeado.
- **Durabilidad:** cola en Postgres con `SELECT ... FOR UPDATE SKIP LOCKED`, **encolada en la misma transacción que el turno**, más la marca de agua `threads.last_consolidated_at`, que delimita la ventana y hace el trabajo idempotente.
- **Orden canónico:** `[system][historial][memoria][mensaje nuevo]`, con la memoria al final, inmediatamente antes del mensaje nuevo, y de forma **transitoria**: no se persiste en el estado del hilo.

## Alternativas consideradas
- **`BackgroundTask`:** descartado; sin durabilidad ni exclusión mutua entre workers.
- **`arq` + Redis:** mejor latencia, pero un servicio más y encolado no transaccional.
- **`pgmq`:** válido y evita código propio, pero no superaba la ventaja del encolado transaccional.
- **Barrido sin cola:** descartado; no garantiza que el turno se procese.

## Consecuencias
- Por qué la memoria va al final y no se persiste: mantener `[system][historial]` byte-estable permite reintentar la respuesta facturando solo el tramo final. Persistirla la repetiría una vez por turno, inflaría el prompt y mostraría recuerdos obsoletos.
- Nada volátil al inicio del prompt (hora, ids de request, contadores); los hechos se escriben en orden de inserción.
- Sin ventana de inconsistencia y sin servicio extra que operar.
- Cuesta 2× por turno y deja el costo de la memoria creciente: se vigila con la métrica de tokens inyectados; compactación y dedup semántica solo en Fase 7.
- Si algún día sube `N`, hace falta *flush* al cerrar el hilo (con `N=1` no es necesario).
