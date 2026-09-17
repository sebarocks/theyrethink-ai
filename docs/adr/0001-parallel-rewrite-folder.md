# 0001 — Rewrite en carpeta paralela

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §3 (A7), §7, §12 Fase 6; plan §5 Fase 0

## Contexto
El proyecto actual (`theythink-ai`) mezcla la lógica del agente con SQL y con HTTP, pero es la única referencia de features y de datos a migrar. Evolucionar in-place obligaría a convivir con ese código y perdería el punto de comparación.

## Decisión
El rewrite vive en una carpeta paralela, **`theyrethink-ai`**. `theythink-ai` queda como referencia de features y datos, en **solo lectura**.

## Alternativas consideradas
- **Evolución in-place:** descartada; contamina la referencia y mezcla el código viejo con el nuevo, sin comparación posible feature a feature.

## Consecuencias
- Permite leer y portar features, y migrar datos con `scripts/migrate_from_sqlite.py` (Fase 5).
- `theythink-ai` se archiva (tag/read-only) al cerrar la Fase 6.
- Cuesta duplicación temporal: seed, prompts y paridad funcional se portan a mano.
- Obliga a: nadie modifica, formatea ni ejecuta scripts de `theythink-ai` (AGENTS.md §1).
