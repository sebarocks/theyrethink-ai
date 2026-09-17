# 0007 — Toolchain obligatorio: `uv` y Deno

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §4; plan §5 Fase 0; AGENTS.md §2

## Contexto
El rewrite necesita un entorno reproducible y verificable en CI desde el primer día. El proyecto actual no lo tiene, y admitir instalaciones ad hoc (pip, npm) reabre el problema en cuanto alguien depura a mano.

## Decisión
Python con **`uv`**: prohibido `pip`, `pip3`, `requirements.txt`, `poetry`, `conda`, `pipenv` y `virtualenv` manual; el pin vive en `uv.lock` versionado, la versión de Python en `.python-version` y todo se ejecuta con `uv run`. Frontend con **Deno**: prohibido `node`, `npm`, `npx`, `pnpm` y `yarn`; configuración en `deno.json` y pin en `deno.lock`, ambos versionados.

## Alternativas consideradas
- **`pip` + `requirements.txt`, `poetry` o `conda`:** descartados; sin lockfile único versionado ni resolución reproducible.
- **Node/npm en el frontend:** descartado; `deno fmt`, `deno lint`, `deno check` y `deno test` sustituyen a Prettier, ESLint, `tsc` y Vitest, sin añadir esas herramientas.

## Consecuencias
- CI con `astral-sh/setup-uv` y `denoland/setup-deno`; **prohibido `actions/setup-node`**.
- Un paquete que solo exista en npm se consume con el especificador `npm:`, nunca instalándolo con npm.
- El `Makefile` es un envoltorio fino sobre `uv run` y `deno task`; no se duplican comandos.
- Cuesta: SvelteKit bajo Deno es el camino menos transitado (spike S6). Si una tarea no se puede hacer sin Node, se detiene y se reporta en vez de instalarlo.
