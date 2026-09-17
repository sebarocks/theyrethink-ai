# S6 — ¿Se puede construir SvelteKit (SPA) íntegramente con Deno, sin Node?

**VEREDICTO: viable con mitigaciones.** SvelteKit + Tailwind + tests + E2E se levantan, tipan y
construyen con Deno 2.9.6 sin ningún binario de Node en el `PATH`. Las mitigaciones son
obligatorias y están acotadas: (1) Deno **materializa `node_modules`** porque Vite resuelve
módulos por sistema de archivos — colisiona con la letra de `AGENTS.md` §2 y exige una excepción
registrada; (2) hacen falta **tres entradas extra en el import map** para los *internals* de
`@sveltejs/kit`; (3) `deno fmt` **no formatea `.svelte`**; (4) `@testing-library/svelte` **no
funciona** (se usa `mount` de Svelte, que sí funciona); (5) el andamiaje oficial `sv` **siempre
escribe `package.json`**, así que el `deno.json` se mantiene a mano. No hay que cambiar de
framework ni activar el plan B (Fresh): el coste de Deno es de *build-time* y no llega a
producción, exactamente como anticipaba el plan §4.13.

- **Fecha:** 2026-09-16
- **Entorno:** Deno 2.9.6 (stable, x86_64-unknown-linux-gnu), V8 15.0, TypeScript 6.0.3
  (el que trae Deno). Sin `pip`, `npm`, `npx`, `yarn` ni `pnpm`: **no se usó ni una vez**.
- **Espacio de trabajo:** `/tmp/spike-s6/base` (fuera del repo, según lo pedido). El proyecto
  quedó íntegro y reproducible; los logs crudos están en `/tmp/spike-s6/*.log`.

---

## 1. Qué funcionó (con los comandos exactos)

### 1.1 Andamiaje

```sh
deno run -A npm:sv@latest create base --template minimal --types ts --no-add-ons --no-install \
  --no-dir-check --no-download-check
```

`sv` es el CLI oficial de Svelte (`sv@0.17.0`). Genera `package.json`, `.npmrc` y `.vscode/`,
que **hay que borrar**: en este proyecto el manifiesto es `deno.json`.

Hallazgo importante: `sv create --install deno` (probado en `/tmp/spike-s6/svdeno`) **también
genera `package.json`** y ejecuta `deno install` sobre él. Es decir, el soporte "deno" de `sv`
significa "Deno como gestor de `package.json`", no "proyecto sin `package.json`". El andamiaje
del repo tendrá que ser: `sv create --no-install` → borrar `package.json`/`.npmrc`/`.vscode` →
escribir `deno.json`. Además, el add-on `sveltekit-adapter` con `adapter:static` genera
`adapter()` **sin `fallback`**, así que el modo SPA se configura a mano de todos modos.

Nota secundaria: con SvelteKit 2.70 / `vite-plugin-svelte` 7 **ya no existe `svelte.config.js`**;
el adapter se declara dentro de `sveltekit({...})` en `vite.config.ts`.

### 1.2 `deno.json` de referencia (esto es lo que funcionó)

```jsonc
{
  "nodeModulesDir": "auto",
  "tasks": {
    "sync": "deno run -A npm:@sveltejs/kit@^2.63.0 sync",
    "dev": "deno run -A npm:vite dev",
    "build": "deno run -A npm:vite build",
    "preview": "deno run -A npm:vite preview",
    "check": "deno check src/ && deno run -A npm:svelte-check@^4 --tsconfig ./tsconfig.json",
    "test": "deno test -A tests/ --ignore=tests/vitest",
    "test:unit": "deno run -A npm:vitest@^5 run",
    "test:e2e": "deno test -A e2e/",
    "fmt": "deno fmt && deno run -A tools/fmt_svelte.ts src/routes src/lib"
  },
  "imports": {
    "vite": "npm:vite@^8.0.16",
    "svelte": "npm:svelte@^5.56.1",
    "tailwindcss": "npm:tailwindcss@^4.1.0",
    "@tailwindcss/vite": "npm:@tailwindcss/vite@^4.1.0",
    "@sveltejs/kit": "npm:@sveltejs/kit@^2.63.0",
    "@sveltejs/kit/vite": "npm:@sveltejs/kit@^2.63.0/vite",
    "@sveltejs/kit/internal": "npm:@sveltejs/kit@^2.63.0/internal",
    "@sveltejs/kit/internal/server": "npm:@sveltejs/kit@^2.63.0/internal/server",
    "@sveltejs/adapter-static": "npm:@sveltejs/adapter-static@^3.0.0",
    "@sveltejs/vite-plugin-svelte": "npm:@sveltejs/vite-plugin-svelte@^7.1.2",
    "vitest": "npm:vitest@^5.0.1",
    "jsdom": "npm:jsdom@^26.0.0",
    "@std/assert": "jsr:@std/assert@^1",
    "@std/testing": "jsr:@std/testing@^1",
    "@std/expect": "jsr:@std/expect@^1",
    "playwright": "npm:playwright@^1.63.0",
    "prettier": "npm:prettier@^3",
    "prettier-plugin-svelte": "npm:prettier-plugin-svelte@^3"
  }
}
```

**`nodeModulesDir: "auto"` no es opcional** (ver §2.1). Versiones resueltas y verificadas:

| Paquete | Resuelto | Paquete | Resuelto |
|---|---|---|---|
| Deno | 2.9.6 | `tailwindcss` / `@tailwindcss/vite` | 4.3.3 |
| `vite` | 8.3.0 (usa rolldown) | `vitest` | 5.0.1 |
| `svelte` | 5.57.0 | `jsdom` | 26.1.0 |
| `@sveltejs/kit` | 2.70.3 | `playwright` / `@playwright/test` | 1.63.0 |
| `@sveltejs/adapter-static` | 3.0.10 | `svelte-check` | 4.7.6 |
| `@sveltejs/vite-plugin-svelte` | 7.3.0 | `prettier` / `-plugin-svelte` | 3.9.6 / 3.5.2 |

`deno.lock` se genera y versiona (43 KB, 133 paquetes npm resueltos).

### 1.3 Dev y build de la SPA

```sh
deno task dev     # VITE v8.3.0 ready in 1006 ms → HTTP 200 en http://127.0.0.1:5173/
deno task build   # ✔ done — "Wrote site to build" (112 KB), ~3 s en frío con caché caliente
```

Configuración SPA (D8) verificada:

```ts
// vite.config.ts
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit({ adapter: adapter({ fallback: 'index.html' }) })]
});
```

```ts
// src/routes/+layout.ts
export const prerender = true;
export const ssr = false;
```

Salida real de `build/`: `index.html` (shell con `__sveltekit_*` y `kit.start(...)`),
`_app/immutable/{entry,chunks,nodes,assets}`, `robots.txt`. Con `fallback: 'index.html'`,
SvelteKit avisa `Overwriting build/index.html with fallback page. Consider using a different
name for the fallback.` — funciona, pero lo limpio para D4 (FastAPI) es `fallback: '200.html'`
y que FastAPI sirva `index.html` en rutas desconocidas.

**No aparece ningún `package.json`** en ningún punto del pipeline.

### 1.4 Tailwind 4 vía plugin de Vite

```sh
deno run -A npm:@tailwindcss/vite   # v4, sin PostCSS ni config JS
```

`src/app.css` → `@import "tailwindcss";`, importado desde `+layout.svelte`. Verificado de forma
fuerte (no solo "compila"): el CSS emitido contiene `text-emerald-600` y `font-bold`, y en
Chromium headless el color computado del `<h1>` es `oklch(0.596 0.145 163.225)`, o sea la
utilidad realmente aplicada.

### 1.5 Typecheck

```sh
deno check src/                                                # ✅ solo archivos .ts
deno run -A npm:svelte-check@^4 --tsconfig ./tsconfig.json      # ✅ .svelte + .ts
# → svelte-check found 0 errors and 0 warnings
```

- `deno check` **sí lee el `tsconfig.json` del proyecto** (comprobado: con `tsconfig.json`
  presente resuelve el alias `$lib/greeting.ts`; renombrándolo falla con
  `Import "$lib/greeting.ts" not a dependency and not in import map`). Ignora los `.svelte`:
  recorre solo `.ts`.
- `svelte-check` corre bajo Deno sin problemas y **detecta errores reales**: inyectando
  `const n: number = "esto no es un number"` en `+page.svelte` reporta
  `Type error: Type 'string' is not assignable to type 'number'. (ts)`.
- **Orden obligatorio:** `deno task sync` (o un `build`) antes de cualquier `check`. Sin
  `.svelte-kit/` generado, `svelte-check` muere con
  `Cannot read file '/…/.svelte-kit/tsconfig.json'` y `deno check` con
  `TS5095 / TS5109 Option 'moduleResolution' must be set to 'NodeNext'…`.

### 1.6 Tests

```sh
deno task test        # deno test nativo  → ok | 1 passed | 0 failed
deno task test:unit   # vitest 5.0.1      → Test Files 1 passed (1) | Tests 1 passed (1)
```

- **Deno test nativo** funciona y es la opción para lógica pura (lo que el plan §6 pide para el
  núcleo). Dos ajustes necesarios y ya resueltos en la referencia:
  1. Los tests no pueden vivir en `src/` ni usar el global `Deno` sin más, porque el
     `tsconfig.json` de SvelteKit lo pisa el checker de Deno
     (`TS2304: Cannot find name 'Deno'`). Solución adoptada: tests fuera de `src/` + estilo BDD
     de `@std/testing/bdd` (no toca el global `Deno` en el archivo) y, para E2E,
     `/// <reference lib="deno.ns" />` + `/// <reference lib="dom" />`.
  2. `tsconfig.json` lleva `"exclude": ["node_modules/**", "tests/**", "build/**", ".svelte-kit/**"]`
     para que `svelte-check` no intente tipar archivos con `jsr:`/`npm:` inline (que su
     TypeScript no sabe resolver). `deno test`/`deno check` siguen viéndolos porque se les pasa
     la ruta explícita.
- **Vitest 5.0.1 funciona, incluido test de componente Svelte.** Dos claves:
  - `resolve: { conditions: ['browser'] }` en `vitest.config.ts`. Sin eso, Svelte resuelve su
    build **de servidor** y los tests fallan con
    `` `mount(...)` is not available on the server `` (con Vitest 3 fallaba igual, por eso se
    fija Vitest 5).
  - Renderizar con `mount()`/`unmount()` de `svelte` en vez de `@testing-library/svelte`
    (ver §2.4).

### 1.7 E2E — Playwright **sí** funciona bajo Deno

Este era el riesgo declarado en el plan. Hay **dos** vías y las dos funcionan:

```sh
# (a) Playwright como librería, dentro de deno test + file-server nativo de Deno
deno run -A jsr:@std/http@^1/file-server build --port 4173 &
deno task test:e2e
# → SPA: monta y aplica Tailwind ... ok (712ms) | ok | 1 passed | 0 failed

# (b) el runner completo @playwright/test
deno run -A npm:@playwright/test@latest test --config playwright.config.ts
# → Running 1 test using 1 worker | ✓ SPA monta (218ms) | 1 passed (788ms)
```

La descarga del navegador también es 100 % Deno:
`deno run -A npm:playwright@latest install chromium` (Chrome Headless Shell 153.0.8010.12,
114 MB). El proceso hijo del navegador lo lanza Deno (`process.execPath` = `deno`), no Node.

Conclusión para el plan: **no hace falta el "checklist manual" de E2E**, aunque conviene
mantenerlo como red de seguridad documental.

### 1.8 Prueba de independencia de Node

Repetido el pipeline entero con un entorno sin Node en el `PATH`
(`env -i HOME=… PATH=…/.deno/bin:/usr/bin:/bin`): `deno task build`, `deno task test:unit` y
`deno task test:e2e` pasan igual. Node **no participa** en build, typecheck, tests ni E2E.

### 1.9 CI

`deno install --frozen` **funciona sin `package.json`** (exit 0; rematerializa los 133 paquetes
desde la caché en 0,11 s) y deja el proyecto listo para `deno task build`. Es decir, el job de
CI sólo necesita `denoland/setup-deno` — nada de `actions/setup-node` — y puede exigir
lockfile congelado:

```sh
deno install --frozen && deno task sync && deno task check && deno task test \
  && deno task test:unit && deno task build && deno task test:e2e
```

---

## 2. Qué falló (errores literales) y cómo se resolvió

### 2.1 Sin `nodeModulesDir` no hay build: Vite no ve el import map

Primer intento con `"nodeModulesDir": "none"` (el modo "puro", sin `node_modules`):

```
vite.config.ts (1:252) [UNRESOLVED_IMPORT] Could not resolve '@sveltejs/adapter-auto' in vite.config.ts
vite.config.ts (2:26) [UNRESOLVED_IMPORT] Could not resolve '@sveltejs/kit/vite' in vite.config.ts
vite.config.ts (3:29) [UNRESOLVED_IMPORT] Could not resolve 'vite' in vite.config.ts
   ╰──── Module not found, treating it as an external dependency
```

**Causa:** Vite empaqueta `vite.config.ts` con esbuild y resuelve bare specifiers por el sistema
de archivos (resolución Node), no por el import map de Deno. Lo mismo vale para todo lo que
resuelve rollup/esbuild en el build.
**Mitigación (la que se adoptó):** `"nodeModulesDir": "auto"`. Deno crea `node_modules/`
—191 MB con todo el tooling de test, 72 MB sin él, 133 paquetes en `node_modules/.deno/`—
mediante symlinks a su caché global. **No hay nada de npm**: es Deno materializando su propia
caché para satisfacer a Vite. A cambio, `node_modules` debe seguir en `.gitignore` (el
`.gitignore` que genera `sv` ya lo incluye).

⚠️ **Trampa a documentar:** Deno también escribe `node_modules/.bin/*` con shebang
`#!/usr/bin/env node` (`vite`, `svelte-kit`, `tsc`…). Invocar esos shims **sí** requiere Node.
Regla para Fase 4: **nunca** ejecutar `node_modules/.bin/<tool>`; siempre
`deno run -A npm:<paquete>` o `deno task`.

### 2.2 El worker de prerender no resuelve los *internals* de kit

Con `nodeModulesDir: "auto"` el build de cliente pasaba y moría en el postbuild:

```
error: Uncaught (in worker "") (in promise) TypeError: Import "@sveltejs/kit/internal/server" not a dependency and not in import map from "file:///tmp/spike-s6/base/.svelte-kit/output/server/index.js"
  hint: If you want to use a JSR or npm package, try running `deno add jsr:@sveltejs/kit/internal/server` or `deno add npm:@sveltejs/kit/internal/server`
```

Es *whack-a-mole*: al declarar `internal/server` aparece `@sveltejs/kit/internal`, y luego
`@sveltejs/kit`. **Los comodines de prefijo no sirven** para esto:

```
TypeError: Failed to resolve the specifier ""@sveltejs/kit/internal/server"" as its after-prefix portion ""internal/server"" could not be URL-parsed relative to the URL prefix "npm:@sveltejs/kit@^2.63.0/" mapped to by the prefix "@sveltejs/kit/"
```

**Mitigación:** declarar las **tres** entradas explícitas en `imports` (`@sveltejs/kit`,
`@sveltejs/kit/internal`, `@sveltejs/kit/internal/server`), como en §1.2. Con eso el build
termina en verde. Ocurre incluso con `ssr = false` porque el prerender necesita montar el shell.

### 2.3 `deno check`/`deno test` y el `tsconfig.json` de SvelteKit chocan por los globales

```
TS2304 [ERROR]: Cannot find name 'Deno'. Do you need to change your target library? Try changing the 'lib' compiler option to include 'deno.ns' or add a triple-slash directive to the top of your entrypoint (main file): /// <reference lib="deno.ns" />
```

Y `deno test` recorriendo la carpeta de Vitest:

```
error: Expected a JavaScript or TypeScript module, but identified a Unknown module. Importing these types of modules is currently not supported.
  Specifier: file:///tmp/spike-s6/base/src/lib/Badge.svelte
```

**Mitigaciones:** tests TS con `/// <reference lib="deno.ns" />` o estilo `@std/testing/bdd`;
`deno test … --ignore=tests/vitest`; y `"exclude"` de `tests/**` en `tsconfig.json` (SvelteKit ya
incluye `tests/**` en su tsconfig generado, así que hay que sobrescribirlo — y al sobrescribir
`exclude` se pierden las exclusiones de `service-worker` de kit: re-listarlas si algún día se
usa service worker).

### 2.4 `@testing-library/svelte` no funciona

```
 FAIL  tests/vitest/Badge.test.ts > renderiza la etiqueta
Svelte error: rune_outside_svelte
The `$state` rune is only available inside `.svelte` and `.svelte.js/ts` files
https://svelte.dev/e/rune_outside_svelte
 ❯ createProps node_modules/.deno/@testing-library+svelte-core@1.1.3/…/src/props.svelte.js:12:22
```

Ninguno de los dos arreglos habituales sirvió (`test.server.deps.inline: ['@testing-library/svelte-core']`
da el mismo error; subir a Vitest 5 tampoco). El archivo `.svelte.js` de
`@testing-library/svelte-core` no pasa por el compilador de Svelte dentro de `node_modules`.
**Mitigación validada:** renderizar con `mount()`/`unmount()` de `svelte` y consultar el DOM con
`document.querySelector`. Es una pérdida menor (`getByRole`/`userEvent` de testing-library) y
tiene plan B: `@testing-library/dom` (sin el wrapper Svelte) para utilidades de consulta.

### 2.5 `deno fmt` ignora `.svelte` (silenciosamente)

```sh
$ deno fmt src/lib/Messy.svelte
Checked 1 file          # …y el archivo sigue mal formateado
```

`deno fmt` sí formatea `.ts`, `.json`, `.md`, `.css` y `.html`, pero **salta `.svelte` sin
avisar** (dice "Checked 1 file"). Es decir, `deno fmt` no cubre el formato del 100 % del código
del frontend, y un CI que sólo corra `deno fmt --check` dejaría pasar componentes sin formatear.
**Mitigación validada** (`tools/fmt_svelte.ts`): Prettier 3.9.6 + `prettier-plugin-svelte` 3.5.2
invocados **como módulos desde un script Deno** (con `npm:`/bare specifiers en el import map):

```ts
import * as prettier from "prettier";
import * as sveltePlugin from "prettier-plugin-svelte";
// …prettier.format(source, { parser: "svelte", plugins: [sveltePlugin], useTabs: true })
```

Resultado real: `<script>` mal indentado, `import   "../app.css"` y `class="a"   ` salen
formateados correctamente. Prettier **solo** por CLI no basta:

```
[error] Cannot find package 'prettier-plugin-svelte' imported from /tmp/spike-s6/base/noop.js
```

(Prettier resuelve los plugins con resolución Node sobre un archivo sintético; desde un script
Deno que importa el plugin de verdad, sí funciona.)
**Decisión pendiente:** `AGENTS.md` §2 dice que `deno fmt` sustituye a Prettier. La mitigación
usa Prettier *como librería* sólo para `.svelte`. Hay dos salidas y hace falta elegir una y
registrarla: (a) `deno fmt` canónico + Prettier-solo-para-svelte como tarea `fmt:svelte`
(excepción explícita en `AGENTS.md` + ADR); (b) `deno fmt` canónico y `.svelte` sin formateo
automático (sólo LSP del editor). Recomiendo (a): sin ella, el código Svelte es el único que
no pasa por ninguna herramienta en CI.

### 2.6 Detalles menores (no bloqueantes)

- `deno lint` falla con `no-import-prefix` si se importan `npm:`/`jsr:` inline en los tests:
  `= hint: Add it as a dependency in a deno.json or package.json instead and reference it here
  via its bare specifier`. Se resuelve declarándolos en `imports` (ya está en §1.2).
- El mensaje final del build dice `Run npm run preview to preview your production build
  locally.` Es cosmético (kit asume scripts de npm); el preview real es
  `deno run -A npm:vite preview`.
- `vite-plugin-svelte` 7 ya no acepta la opción `hot` en la config inline
  (`invalid plugin option 'hot' in inline config`) y avisa
  `no Svelte config found at … - using default configuration.` por la desaparición de
  `svelte.config.js`. Ambos avisos son inocuos.
- El andamiaje deja `.vscode/` (y `.npmrc` que impone `engine-strict`): borrarlos.

---

## 3. Riesgos y workarounds

| # | Riesgo | Impacto | Workaround / decisión |
|---|---|---|---|
| R1 | `node_modules` materializado por Deno (`nodeModulesDir: "auto"`) | Choca con `AGENTS.md` §2 ("no se crea ni se versiona `node_modules`") | **Excepción explícita + ADR.** Es generado por Deno, no por npm, y va en `.gitignore`. No hay alternativa: Vite resuelve por FS. Presupuesto: 72 MB (build) / 191 MB (con E2E y Prettier) |
| R2 | `node_modules/.bin/*` con shebang `node` | Tentación de invocar el shim y depender de Node | Regla dura: siempre `deno run -A npm:<pkg>` / `deno task`; prohibido `./node_modules/.bin/*` |
| R3 | Ecosistema Svelte cambia rápido (Vite 8 + rolldown, kit 2.70, `svelte.config.js` desaparecido); el import map debe declarar internals de kit | Un `minor` de kit puede romper el build | Fijar versiones en `deno.json` + `deno.lock` versionado; el error es explícito (`not in import map`) y se arregla añadiendo la entrada |
| R4 | `@testing-library/svelte` inservible | Tests de componente menos ergonómicos | `mount()`/`unmount()` de Svelte + `document.querySelector`; opcionalmente `@testing-library/dom` |
| R5 | `deno fmt` no cubre `.svelte` | Código Svelte sin formato en CI | `tools/fmt_svelte.ts` (Prettier como librería) como `deno task fmt`; requiere excepción en `AGENTS.md` |
| R6 | Orden `sync` → `check` | CI rojo confuso (`Cannot read file .svelte-kit/tsconfig.json`) | Encadenar en el `Makefile`: `check` depende de `sync` |
| R7 | `deno test` no puede recorrer tests que importen `.svelte` | El glob de tests se rompe | Convención de carpetas: `tests/` (Deno test), `tests/vitest/` (Vitest, excluido con `--ignore`), `e2e/` (Playwright + `deno test`) |
| R8 | **E2E**: Playwright era el mayor riesgo declarado | Bloqueaba el DoD de Fase 4 | **Resuelto: funciona.** Librería dentro de `deno test` y runner `@playwright/test`; `deno run -A npm:playwright install chromium` para el navegador. Red de seguridad: checklist manual si un día se rompe |
| R9 | Playwright descarga binarios en CI (114 MB) + `webServer` del config no probado | Jobs lentos; el arranque del backend en E2E no se validó aquí | Cachear `~/.cache/ms-playwright` en CI; para E2E de Fase 4 levantar FastAPI con `uv run uvicorn` y usar `baseURL`/`webServer` (verificar en su momento) |
| R10 | `jsr:`/`npm:` inline disparan `no-import-prefix` | `deno lint` rojo | Declarar todo en `imports` del `deno.json` |
| R11 | D9 (i18n) sigue abierta | Bloquea Fase 4 | El add-on `paraglide` existe en `sv`, pero **no se probó** y sería un paquete npm vía `npm:`. No se decide aquí |
| R12 | `deno check` solo tipa `.ts` (nunca `.svelte`) | Falsa sensación de cobertura | `check` = `deno check src/` **&&** `svelte-check`; ambos en CI |

---

## 4. Recomendación para Fase 4 (accionable)

1. **Adelante con SvelteKit + Deno. No activar el plan B (Fresh).** El riesgo queda confinado al
   build-time por D8, y los tres puntos "frágiles" del plan §2 —plugins de Vite, `svelte-check`
   y Playwright— **quedaron verificados**: Tailwind, typecheck y E2E funcionan. Vitest también,
   con la excepción de `@testing-library/svelte`.
2. **Registrar la excepción de `node_modules` y el formato de `.svelte`** (§2.1, §2.5) como ADR
   **antes** de escribir código, y mapearlo en el plan §3. Sin eso, el repo nace violando sus
   propias reglas; con eso, la regla es explícita y auditable. Texto sugerido para `AGENTS.md`
   §2: *"`node_modules` puede existir en el frontend porque Vite lo exige para resolver módulos;
   lo genera Deno (`nodeModulesDir: "auto"`), nunca npm, y está en `.gitignore`. Prohibido
   invocar `node_modules/.bin/*`."*
3. **Adoptar el `deno.json` de §1.2 como plantilla** (tareas `sync`/`dev`/`build`/`preview`/
   `check`/`test`/`test:unit`/`test:e2e`/`fmt`) y hacer que el `Makefile` delegue en él. Las
   tareas canónicas de `AGENTS.md` §2 se cumplen tal cual.
4. **Andamiaje:** `sv create --no-install` → borrar `package.json`, `.npmrc`, `.vscode` →
   escribir `deno.json` + `deno.lock`. Fijar las versiones del §1.2 y commitear `deno.lock`.
5. **SPA:** `adapter-static` con `fallback: '200.html'` (mejor que `index.html`, que kit
   sobrescribe con aviso) y `+layout.ts` con `prerender = true` / `ssr = false`. FastAPI (D4)
   sirve `build/` y devuelve el shell en rutas no encontradas.
6. **Convención de tests desde el día uno:** `tests/` (Deno test, lógica pura e i18n —p. ej. el
   test de paridad de claves de 6 idiomas—), `tests/vitest/` (componentes con `mount`),
   `e2e/` (Playwright). Con eso el DoD de Fase 4 ("E2E smoke verde") es automatizable, no un
   checklist manual.
7. **CI:** sólo `denoland/setup-deno`; `deno install --frozen && deno task sync && deno task
   check && deno task test && deno task test:unit && deno task build && deno task test:e2e`,
   cacheando `~/.cache/deno` y `~/.cache/ms-playwright`.
8. **Cerrar S3 (SSE) en el mismo espíritu:** el runtime real del frontend es el navegador sobre
   estáticos servidos por FastAPI; nada de esto depende de Deno en producción.

---

## 5. Respuestas directas a las preguntas del spike

| # | Pregunta | Respuesta |
|---|---|---|
| 1 | ¿SvelteKit mínimo con `deno.json` (`npm:`) sin `package.json`? ¿Aparece `node_modules`? | **Sí al primero, sí al segundo.** `dev`, `build` y `preview` funcionan sin `package.json`. `node_modules` lo crea Deno (`nodeModulesDir: "auto"`): imprescindible para que Vite resuelva, 72–191 MB, 133 paquetes en `node_modules/.deno/` |
| 2 | ¿`adapter-static` con `ssr = false` + `fallback`? | **Sí.** Produce `build/index.html` (shell SPA) + `_app/immutable/*`. Con `fallback: 'index.html'` kit avisa que sobrescribe el index; usar `'200.html'` |
| 3 | ¿Tailwind vía plugin de Vite? | **Sí.** `@tailwindcss/vite` 4.3.3 + `@import "tailwindcss"`; verificado por CSS emitido y color computado en el navegador |
| 4 | ¿`deno check` y/o `svelte-check`? | **Ambos.** `deno check` lee el `tsconfig.json` del proyecto (alias `$lib` OK) pero sólo tipa `.ts`; `svelte-check` vía `deno run -A npm:svelte-check` cubre `.svelte` y detecta errores reales. Requieren `sync` previo |
| 5 | ¿Tests? | **Los dos caminos.** `deno test` nativo (con `--ignore` de la carpeta Vitest y cuidado con el global `Deno` frente al tsconfig de kit) y **Vitest 5.0.1** con tests de componente, usando `mount()` de Svelte |
| 6 | ¿Qué falla y con qué error? | §2: `UNRESOLVED_IMPORT` sin `nodeModulesDir: "auto"`; `not a dependency and not in import map` para los internals de kit (los comodines de prefijo no valen); `rune_outside_svelte` y `mount(...) is not available on the server` en Vitest/testing-library; `deno fmt` ignora `.svelte`; `Cannot find package 'prettier-plugin-svelte'` en la CLI de Prettier; `no-import-prefix` de `deno lint` |

---

## 6. Evidencia

- Proyecto del spike: `/tmp/spike-s6/base` (reproducible; `deno.json`, `deno.lock`,
  `vite.config.ts`, `vitest.config.ts`, `tsconfig.json` con `exclude`, `tools/fmt_svelte.ts`,
  `tests/`, `tests/vitest/`, `e2e/`, `e2e-runner/`, `playwright.config.ts`).
- Segundo andamiaje (para probar `sv --install deno`): `/tmp/spike-s6/svdeno`.
- Logs crudos: `build1.log`, `build2.log`, `build3.log`, `build-tw.log`, `build-final.log`,
  `vitest.log`, `vitest2.log`, `vitest4.log`, `vitest6.log`, `e2e.log`, `pw-install.log`,
  `pwtest.log`, `dev.log`, `dev2.log`, `serve.log`.
- Todo lo anterior vive fuera del repositorio; **este documento es el único archivo escrito en
  `theyrethink-ai`** y no se tocó ningún otro archivo del proyecto.
