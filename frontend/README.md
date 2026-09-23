# Frontend

SvelteKit en modo **SPA** (D8) sobre **Deno**, servido por FastAPI (D4). El
andamiaje arrancó en la **Fase 4**; ver `DEVELOPMENT_PLAN.md` §5.

## Estructura

```
deno.json              # manifiesto: tareas e import map (npm:/jsr:)
deno.lock              # lockfile versionado
vite.config.ts         # SPA (adapter-static) + Tailwind + Paraglide
vitest.config.ts       # tests de componente (resolve.conditions: ['browser'])
tsconfig.json          # extiende .svelte-kit/tsconfig.json; allowImportingTsExtensions
project.inlang/        # configuración de i18n (locales y patrón de mensajes)
messages/{locale}.json # traducciones: es, en, fr, pt, ko, zh
src/app.html           # shell + script anti-parpadeo de tema
src/app.css            # Tailwind (build de Vite, no CDN)
src/routes/            # +layout (shell + guarda de sesión), +page, login, web|whatsapp|telegram/[agent]
src/lib/api/           # cliente generado + client.ts + errors.ts + auth/agents/threads/chat
src/lib/chat/          # Chat, Composer, MessageBubble, sse.ts y skins/
src/lib/session.ts     # estado de sesión (svelte/store)
src/lib/theme.ts       # tema claro/oscuro
src/lib/paraglide/     # GENERADO por Paraglide; no se versiona
tools/fmt_svelte.ts    # Prettier como librería para los .svelte
tests/                 # Deno test (lógica pura: paridad i18n, parser SSE)
tests/vitest/          # componentes con mount() de Svelte
e2e/                   # Playwright (Fase 4, pendiente)
```

## Comandos

| Quiero                                    | Comando                             |
| ----------------------------------------- | ----------------------------------- |
| Dev                                       | `deno task dev`                     |
| Build de la SPA                           | `deno task build`                   |
| Typecheck (`deno check` + `svelte-check`) | `deno task sync && deno task check` |
| Compilar i18n (Paraglide)                 | `deno task i18n`                    |
| Tests de lógica pura                      | `deno task test`                    |
| Tests de componente                       | `deno task test:unit`               |
| E2E                                       | `deno task test:e2e`                |
| Formato (incluye `.svelte`)               | `deno task fmt`                     |
| Lint                                      | `deno task lint`                    |
| Regenerar el cliente API                  | `deno task openapi`                 |

El `Makefile` de la raíz expone `frontend-dev`, `frontend-build`,
`frontend-check`, `frontend-test`, `frontend-lint` y `frontend-fmt`.

## Restricciones ya validadas (spike S6)

Las conclusiones de
[`../docs/spikes/S6-sveltekit-deno.md`](../docs/spikes/S6-sveltekit-deno.md)
condicionan cómo se monta:

- **`nodeModulesDir: "auto"` es obligatorio.** Vite resuelve imports por sistema
  de archivos, no por el import map; sin esa opción el build muere con
  `[UNRESOLVED_IMPORT]`.
- **Deno genera y materializa `node_modules`.** Es una excepción explícita a la
  regla de `AGENTS.md` §2 — el árbol lo produce Deno, no npm, y se ignora en
  git.
- **Nunca invoques los shims de `node_modules/.bin/`**: llevan shebang
  `#!/usr/bin/env node`. Siempre `deno run -A npm:<paquete>`.
- **`deno fmt` ignora los archivos `.svelte` en silencio**: se formatean con
  Prettier y `prettier-plugin-svelte` invocados como librería desde
  `tools/fmt_svelte.ts`.
- `@testing-library/svelte` no funciona bajo Deno; se usa `mount()` de Svelte.
- Vitest requiere `resolve.conditions: ['browser']`.
- **Orden obligatorio:** `deno task sync` (o un `build`) antes de
  `deno task check`.
- **Extensiones `.ts` en imports:** `deno check` las exige y `svelte-check` las
  prohíbe; se resuelve con `allowImportingTsExtensions: true` en `tsconfig.json`
  (ya aplicado).
- **Cliente generado:** se regenera con `--default-non-nullable false` para que
  los campos con `default` en el OpenAPI queden opcionales en TypeScript.

## i18n (D9, ADR 0019)

Paraglide JS compila `messages/{locale}.json` a funciones ESM tipadas (`m.*`).
La locale se persiste en `localStorage`. El **test de paridad**
(`tests/i18n_parity_test.ts`) falla si las 6 locales no declaran exactamente las
mismas claves.

Las **464 claves × 6 locales** se portaron del proyecto anterior con
`scripts/port_i18n.ts` (una vez; solo lectura sobre `../theythink-ai`). El
script conserva las claves ya presentes, así que re-ejecutarlo no borra trabajo
posterior.

Ver `DEVELOPMENT_PLAN.md` §5 (Fase 4) y `docs/adr/0018-*`, `docs/adr/0019-*`.
