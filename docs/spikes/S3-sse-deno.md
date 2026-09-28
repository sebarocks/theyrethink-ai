# S3 — SSE a través de Deno y del cliente generado

- **Fecha:** 2026-09-16 · **cierre:** 2026-09-28
- **Estado:** ✅ concluido — transporte verificado y protocolo cerrado con el endpoint de la Fase 3
- **Bloquea:** Fase 3 (protocolo) y Fase 4 (tooling) — ambas cerradas
- **Ámbito:** Deno 2.9.6 en `frontend/`

## Pregunta

¿Se puede consumir SSE con `fetch` + `ReadableStream` bajo Deno, con cookies `SameSite`, y
qué queda por decidir?

## Lo que se ejecutó

Un servidor efímero en Deno que emite un flujo `text/event-stream`, consumido con `fetch` y
leído con `ReadableStream` + `TextDecoder`. Sin SvelteKit de por medio: se aísla el transporte.

## Resultados

```
content-type: text/event-stream
eventos recibidos: "event: token\ndata: uno\n\ndata: dos\n\n"
```

El transporte funciona: `fetch` + streaming de la respuesta + decodificación incremental, con
el runtime de Deno. La mitad "¿Deno puede?" está respondida.

## Lo que aporta S6 (spike hermano)

El spike [S6](./S6-sveltekit-deno.md) validó que la cadena SvelteKit + Tailwind + typecheck +
tests + E2E se construye bajo Deno. Es decir: ni el runtime ni el tooling del frontend son un
impedimento para el streaming.

## Lo que queda abierto (Fase 3)

Son decisiones de diseño, no incógnitas técnicas, y se resuelven al implementar el endpoint:

1. **Formato del evento**: nombres de evento (`token`, `done`, `error`), y si el `done` lleva
   metadatos (id del mensaje, tokens usados, memoria consolidada).
2. **Errores a mitad de stream**: el status HTTP ya se envió, así que la forma
   `{error, code, detail}` tiene que viajar **dentro** del stream. Hay que definirlo ahora para
   no inventarlo en el frontend.
3. **Heartbeat** para atravesar proxies que cortan conexiones ociosas.
4. **Cancelación**: el cliente corta; el backend debe abortar la llamada al LLM y **aun así**
   encolar la consolidación con lo que alcanzó a responder.
5. **Reconexión**: si se corta, ¿se reanuda o se muestra reintento? Recomendado: reintento
   simple en v1, sin `Last-Event-ID`.
6. **Cookies**: con el mismo origen (D4) basta `SameSite=Lax`; conviene verificar que el
   `fetch` de streaming envía la cookie y que la respuesta puede leerla el frontend.

## Recomendación

No requiere más spikes. El punto 2 (forma del error dentro del stream) es el único que conviene
decidir **antes** de escribir el cliente, porque condiciona el contrato generado.

## Cierre (2026-09-28)

El protocolo se implementó en la Fase 3 (`backend/app/api/v1/chat.py`) y el cliente lo consume
en la Fase 4 (`frontend/src/lib/api/chat.ts`, parser puro en `frontend/src/lib/chat/sse.ts`).
Los seis puntos abiertos quedaron resueltos así:

1. **Formato del evento:** `event: chunk` con `data: {"text", "done"}`; `event: done` cierra;
   `event: heartbeat` con `data: {}` mantiene viva la conexión y lo descarta el parser.
2. **Errores a mitad de stream:** viajan **dentro** del stream como `event: error` con
   `data: {"code", "detail"}`, mismo shape `{error, code, detail}` que el envelope REST. El
   cliente los expone como `{ type: "error" }` sin romper el generador.
3. **Heartbeat:** emitido cada 15 s mientras se espera un chunk del proveedor
   (`HEARTBEAT_SECONDS`).
4. **Cancelación:** el cliente corta con `AbortSignal`; el backend cancela la tarea productora
   y hace `rollback` de la transacción pendiente. El cierre del turno (`record_turn` + `commit`
   + `done`) solo ocurre cuando el proveedor termina.
5. **Reconexión:** reintento simple en v1; **sin** `Last-Event-ID`.
6. **Cookies:** mismo origen (D4) con `credentials: "include"` en el cliente generado;
   `SameSite=Lax` basta. Verificado además en el E2E de la Fase 4, que ejerce un turno SSE
   completo sobre el cliente generado.

El **E2E smoke** (`frontend/e2e/smoke_test.ts`, Playwright bajo Deno) ejerce el flujo
login → agentes → chat con streaming → skins → logout y cierra la verificación de tooling que
S3 compartía con S6.