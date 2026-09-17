# S3 — SSE a través de Deno y del cliente generado

- **Fecha:** 2026-09-16
- **Estado:** 🟡 parcial — la mitad de transporte está verificada; el protocolo se cierra en la Fase 3
- **Bloquea:** Fase 4 (tooling) y Fase 3 (protocolo)
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