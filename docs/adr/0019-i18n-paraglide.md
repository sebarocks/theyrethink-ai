# 0019 — i18n con Paraglide JS

- **Estado:** aceptada
- **Fecha:** 2026-09-23
- **Fuente:** propuesta §4, §9.3, §14 (D9); plan §3, §5 Fase 4

## Contexto

El frontend necesita i18n en 6 idiomas (es, en, fr, pt, ko, zh) con paridad de claves, y **D9**
(librería) estaba abierta y bloqueaba la Fase 4. El proyecto actual resuelve el idioma con
diccionarios JS en runtime (`i18n*.js`), sin tipado de claves ni *tree-shaking*.

## Decisión

**Paraglide JS** (`@inlang/paraglide-js`, v2) como sistema único de i18n, con los mensajes en
`messages/{locale}.json` y compilación en *build-time* vía el plugin de Vite. La locale se
persiste en `localStorage` (estrategia `localStorage` → `preferredLanguage` → `baseLocale`).

## Alternativas consideradas

- **typesafe-i18n, `svelte-i18n`, i18next, Lingui, Fluent (`@nubolab/svelte-fluent`) y una
  solución propia mínima:** descartadas frente a Paraglide por ser *compile-time* y
  *tree-shakeable* (los mensajes no usados no llegan al bundle), con tipado de claves y
  parámetros, y por ser la integración oficial de i18n de SvelteKit.

## Consecuencias

- Las claves se compilan a funciones ESM tipadas (`m.*`): un *typo* es error de compilación.
- El bundle de i18n se reduce por *tree-shaking*; no hay resolución de diccionarios en runtime.
- El directorio generado `src/lib/paraglide/` **no se versiona** (lo produce el plugin/CLI).
- `project.inlang/settings.json` es la fuente de locales y del patrón de mensajes: añadir una
  locale o una clave es editar archivos versionados.
- **Paridad de claves obligatoria:** un test de Deno compara el conjunto de claves de las 6
  locales y falla si difieren (invariante de `AGENTS.md` §3.7).
- El compilador resuelve sus *plugins* desde CDN (`modules` en `settings.json`), así que el
  primer build necesita red; queda cacheado después.
- **Riesgo R11 (S6) resuelto:** Paraglide bajo Deno se verificó con el primer
  `deno task build` (compila; `deno check`, `svelte-check`, los tests de paridad y los de
  componente en verde). El plan B (`svelte-i18n` o una solución propia) no hizo falta.
