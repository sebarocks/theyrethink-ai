# Frontend

El frontend (SvelteKit en modo SPA, sobre Deno) se andamia en la **Fase 4**. En la Fase 0
solo existe esta carpeta, a propósito: no se crea un `deno.json` incompleto que falle de
forma confusa.

## Restricciones ya validadas

Las conclusiones del spike **S6** ([`../docs/spikes/S6-sveltekit-deno.md`](../docs/spikes/S6-sveltekit-deno.md))
condicionan cómo se monta:

- **`nodeModulesDir: "auto"` es obligatorio.** Vite resuelve imports por sistema de archivos,
  no por el import map; sin esa opción el build muere con `[UNRESOLVED_IMPORT]`.
- **Deno genera y materializa `node_modules`.** Es una excepción explícita a la regla de
  `AGENTS.md` §2 — el árbol lo produce Deno, no npm, y se ignora en git.
- **Nunca invoques los shims de `node_modules/.bin/`**: llevan shebang `#!/usr/bin/env node`.
  Siempre `deno run -A npm:<paquete>`.
- **`deno fmt` ignora los archivos `.svelte` en silencio**: se formatean con Prettier y
  `prettier-plugin-svelte` invocados como librería desde un script de Deno.
- `@testing-library/svelte` no funciona bajo Deno; se usa `mount()` de Svelte.
- Vitest requiere `resolve.conditions: ['browser']`.

Ver `DEVELOPMENT_PLAN.md` §5 (Fase 4) y `docs/adr/0018-*`.