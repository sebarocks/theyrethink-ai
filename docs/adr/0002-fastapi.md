# 0002 — FastAPI como framework del backend

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §3 (A1), §4, §8; plan §5 Fase 3

## Contexto
El backend actual es Flask con plantillas Jinja y SQL bloqueante. El rewrite necesita validación de entrada, un contrato tipado con el frontend y ejecución no bloqueante para el streaming (D5) y para `asyncpg` (D15).

## Decisión
El backend se construye con **FastAPI + Pydantic v2**, todo bajo `/api/v1/...`, y el OpenAPI generado es el contrato con el frontend.

## Alternativas consideradas
- **Flask:** descartado; sin validación nativa ni OpenAPI como fuente de verdad.
- **Django:** descartado; su ORM y su capa de plantillas no encajan con SQLModel (A2) ni con SvelteKit (A6).

## Consecuencias
- Habilita validación con Pydantic, async nativo y `/docs` navegable.
- Obliga a: snapshot versionado del OpenAPI y cliente TypeScript regenerado (AGENTS.md §3.5).
- Obliga a disciplina async: ningún `async def` puede llamar código bloqueante (§13).
- Cuesta la familiaridad de Flask/Jinja del proyecto actual; el frontend pasa a SvelteKit.
