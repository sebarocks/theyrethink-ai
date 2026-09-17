# S5 — `import-linter` como guardián de la costura

- **Fecha:** 2026-09-16
- **Estado:** ✅ concluido (contrato en `pyproject.toml`, verificado en CI local)
- **Bloquea:** Fase 0
- **Ámbito:** `backend/pyproject.toml` y `backend/app/`

## Pregunta

¿`import-linter` puede impedir que `langgraph`/`langchain` se importen fuera de
`app/agent/`, con la estructura propuesta?

## Lo que se ejecutó

Dos contratos en `[tool.importlinter]`:

1. **`forbidden`** — `langgraph`, `langchain`, `langchain_core` y `langchain_openai` no
   pueden importarse desde ninguno de los paquetes de `app/` **salvo** `app.agent`.
2. **`layers`** — el núcleo (`app.agent`) no conoce la capa de API (`app.api`).

Verificación real del guardrail: se añadió temporalmente `import langgraph` a `app/main.py`,
se corrió `lint-imports`, y luego se revirtió.

## Resultados

```
# con la violación
app.main is not allowed to import langgraph:
-   app.main -> langgraph (l.56)

# restaurado
Contracts: 2 kept, 0 broken.
```

El contrato **falla cuando debe fallar** y pasa cuando debe pasar. La costura está protegida
por una verificación automática, no por disciplina: quien la rompa se entera en CI.

## Hallazgo — una configuración que no es obvia

Un contrato `forbidden` que nombra paquetes de terceros exige
`include_external_packages = true` en `[tool.importlinter]`. Sin esa opción, `lint-imports`
no arranca. Está documentado en el `pyproject.toml` para que nadie lo quite "porque no se usa".

## Limitación conocida (importante)

El contrato enumera los paquetes de origen uno por uno. **Un paquete nuevo de primer nivel
bajo `app/` no queda cubierto hasta que se añade a `source_modules`.** La alternativa
—un guardián por `grep` en CI— cubriría automáticamente cualquier módulo nuevo.

**Recomendación:** mantener el contrato (expresa la intención y da buenos mensajes) **y**
añadir en la Fase 2 un `grep` de CI como segunda barrera. Hasta entonces, la nota está escrita
junto al propio contrato en `pyproject.toml`.