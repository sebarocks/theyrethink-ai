# 0024 — Render de Markdown sin dependencias y sin `{@html}`

- **Estado:** aceptada
- **Fecha:** 2026-10-01
- **Fuente:** propuesta §10 (paridad: "análisis estructurados en Markdown enriquecido"); revisión previa a la Fase 6

## Contexto

El proyecto viejo renderizaba Markdown con `marked` + `DOMPurify`. En el rewrite los mensajes
del asistente salían como texto plano (`whitespace-pre-wrap`), así que las respuestas con
listas, negritas o bloques de código se veían crudas. La propuesta §10 lo lista como paridad y
la revisión lo marcó como hueco de superficie.

La opción obvia era volver a `marked` + `DOMPurify` por el especificador `npm:` (permitido por
AGENTS.md §2). Implica introducir dos dependencias de runtime, un sanitizador y `{@html}`, que
es donde vive el riesgo de XSS.

## Decisión

Renderizar un **subconjunto de Markdown con un parser propio** (`src/lib/chat/markdown.ts`) que
devuelve bloques y segmentos tipados, y un componente Svelte (`Markdown.svelte`) que los
renderiza como **elementos**. **Nunca se usa `{@html}`**, así que el HTML que venga del modelo
se escapa por construcción: no hay superficie de inyección que sanear.

Cobertura: encabezados (`#`), párrafos, listas con y sin numerar, citas, bloques de código,
negrita, cursiva, código en línea y enlaces. Enlaces: solo `http(s)://`, `mailto:`, rutas
`/` y anclas `#`; cualquier otro esquema (`javascript:`, `data:`) se degrada a texto.

## Alternativas consideradas

- **`marked` + `DOMPurify` vía `npm:`**: más cobertura (tablas, HTML embebido), pero dos
  dependencias, sanitizador y `{@html}`. Descartada: el chat no necesita tablas y la
  superficie de XSS no compensa. Además el entorno de build del proyecto no pudo instalar
  paquetes npm nuevos (caché de Deno de solo lectura), lo que refuerza la opción sin deps.
- **Markdown a Svelte en build time**: inviable, el contenido llega por streaming.

## Consecuencias

- Sin dependencias nuevas ni `{@html}`; el HTML del modelo se muestra como texto.
- Cobertura limitada a propósito: no hay tablas, HTML embebido ni notas al pie. Si hiciera
  falta, se amplía el parser con su test.
- La lógica de parseo es pura y se prueba sin DOM (`tests/markdown_test.ts`); el componente se
  prueba con `mount()` y un caso de `<script>`/`onerror` (`tests/vitest/markdown.test.ts`).
- El mismo componente lo usan `MessageBubble` y las tres skins, así que el render es idéntico
  en los tres canales (invariante de skins, AGENTS.md §3.6).
