# 0015 — SvelteKit en modo SPA servido por FastAPI

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §3 (A6), §4, §9, §14 (D8, D9); plan §2 (S6), §5 Fase 4

## Contexto
El frontend actual son plantillas Jinja con JS duplicado por canal. Hacía falta un framework con bundle pequeño y un solo componente de chat, y decidir si el build produce SPA o SSR.

## Decisión
**SvelteKit con `adapter-static` en modo SPA**, con la salida servida por FastAPI en el mismo origen (D4).

## Alternativas consideradas
- **React, Vue/Nuxt, Astro:** descartados; ergonomía y bundle, y los 3 canales son skins de un mismo componente (A10).
- **Fresh** (nativo de Deno): plan B solo si la compatibilidad con Deno duele.

## Consecuencias
- Deno queda **solo en tiempo de build**: el runtime es FastAPI sirviendo estáticos, así que el riesgo de Deno no llega a producción (spike S6).
- El cliente TypeScript se genera desde el OpenAPI; prohibido escribir `fetch` a mano.
- Tailwind por build de Vite, nunca CDN; el script anti-parpadeo de tema se traslada al layout de SvelteKit.
- Modo SPA: no hay SSR; la navegación y los datos se resuelven en el cliente contra `/api/v1`.
- **D9 sigue abierta:** la librería de i18n (Paraglide, typesafe-i18n, `svelte-i18n`, i18next, Lingui, Fluent o una propia mínima) no está decidida y bloquea la Fase 4.
