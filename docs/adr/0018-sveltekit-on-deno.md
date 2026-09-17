# 0018 — SvelteKit sobre Deno: excepciones verificadas

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** spike S6 (`docs/spikes/S6-sveltekit-deno.md`), `AGENTS.md` §2, D8

## Contexto

El proyecto usa Deno y prohíbe Node y npm (ADR 0007), pero el andamiaje de SvelteKit
(ADR 0015) asume Node: Vite resuelve imports por sistema de archivos y varias herramientas del
ecosistema son CLIs de Node. El spike S6 verificó bajo Deno 2.9.6 qué funciona y qué no.

## Decisión

Se mantiene SvelteKit sobre Deno, con dos excepciones explícitas y acotadas:

1. **`node_modules` generado por Deno.** Se habilita `nodeModulesDir: "auto"` porque sin esa
   opción el build falla con `[UNRESOLVED_IMPORT] Could not resolve 'vite'`. El árbol está en
   `.gitignore` y **jamás** se gestiona con npm. Corolario: **no se invocan los shims de
   `node_modules/.bin/`** (llevan shebang `#!/usr/bin/env node`); la forma canónica es
   `deno run -A npm:<paquete>`.
2. **Prettier solo para `.svelte`.** `deno fmt` ignora los archivos `.svelte` **en silencio**,
   así que se formatean con Prettier + `prettier-plugin-svelte` invocados **como librería**
   desde un script de Deno. No se usa la CLI de Prettier ni npm.

## Alternativas consideradas

- **Fresh** (framework nativo de Deno): elimina la fricción de raíz, pero se descarta como
  plan A porque SvelteKit es más maduro para una SPA y el diseño de `<Chat>` + skins es
  agnóstico del framework. Queda como plan B si la fricción crece.
- **Playwright con Node en CI:** descartado; violaría la regla del proyecto. El spike verificó
  que Playwright funciona bajo Deno, incluido el runner `@playwright/test`.
- **No formatear los `.svelte`:** descartado; dejaría código sin formato de forma silenciosa.

## Consecuencias

- Deno queda **solo en tiempo de build**: con `adapter-static` (D8) el runtime es FastAPI
  sirviendo estáticos, así que estas excepciones no llegan a producción.
- Ya validado: Tailwind vía `@tailwindcss/vite`, `svelte-check`, Vitest (exige
  `resolve.conditions: ['browser']`) y Playwright, incluido el runner.
- **No** funciona `@testing-library/svelte` (error `rune_outside_svelte`): se usa `mount()`.
- Coste: `node_modules` ocupa ~72 MB (191 MB con E2E y Prettier). Se limpia con `deno cache`.
- Si aparece una tarea que no se pueda hacer sin Node, hay que **detenerse y reportarlo**
  (`AGENTS.md` §2); no se instala.