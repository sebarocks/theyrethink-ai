# AGENTS.md — `theyrethink-ai`

Guía obligatoria para agentes de IA y personas que trabajan en este repositorio. Si algo
aquí contradice una instrucción puntual, gana este archivo salvo que el usuario diga lo
contrario de forma explícita.

---

## 1. Contexto y fuentes de verdad

| Documento | Rol |
|---|---|
| `REWRITE_PROPOSAL.md` | **Arquitectura y decisiones.** El registro canónico de decisiones es su §14 |
| `DEVELOPMENT_PLAN.md` | **Ejecución:** fases, DoD, gates y estado |
| `../theythink-ai` | Proyecto anterior: **referencia de features y datos. Solo lectura.** Prohibido modificarlo, formatearlo o ejecutar sus scripts como si fuera este repo |

Reglas de proceso:

- **No inventes arquitectura en el código.** Si aparece una decisión nueva, se registra en la
  propuesta §14 y se mapea en el plan §3 antes de implementarla.
- **No dupliques decisiones** entre documentos: la propuesta manda.
- Un cambio de arquitectura sin ADR en `docs/adr/` se considera incompleto.

---

## 2. Toolchain obligatorio

### Python — `uv` (Astral)

- **Prohibido `pip`, `pip3`, `requirements.txt`, `poetry`, `conda`, `pipenv` y `virtualenv`
  manual.** No hay excepción "temporal".
- El pin de versiones vive en **`uv.lock`, que se versiona**. No se edita a mano.
- Python se fija con `uv python pin <version>`, que produce `.python-version` (versionado).
- Todo comando de Python se ejecuta con `uv run`, nunca con el intérprete suelto.

### Frontend — Deno

- **Prohibido `node`, `npm`, `npx`, `pnpm` y `yarn`.** No se crea ni se versiona
  `package.json`.
- Configuración y tareas en **`deno.json`**; lockfile en **`deno.lock`** (versionado).
- Si necesitas un paquete que solo existe en npm, se consume con el especificador `npm:` o
  con `deno run -A npm:<herramienta>`. **Nunca** instalándolo con npm.
- Si una tarea no se puede hacer sin Node, **detente y repórtalo**; no lo instales por tu
  cuenta.
- **Excepción verificada (spike S6): `node_modules` lo genera Deno, no npm.** Es obligatorio
  (`nodeModulesDir: "auto"`) porque Vite resuelve imports por sistema de archivos y no por el
  import map; sin esa opción el build falla con `[UNRESOLVED_IMPORT]`. Ese árbol está en
  `.gitignore` y **jamás se gestiona con npm**. Ver `docs/adr/0018-*`.
- **Nunca invoques los shims de `node_modules/.bin/`**: llevan shebang `#!/usr/bin/env node`.
  La forma canónica es `deno run -A npm:<paquete>`.
- `deno lint`, `deno check` y `deno test` sustituyen a ESLint, `tsc` y Vitest.
- `deno fmt` **ignora los archivos `.svelte` en silencio**: los `.svelte` se formatean con
  Prettier y `prettier-plugin-svelte` invocados **como librería** desde un script de Deno (no
  como CLI, no vía npm). Ver `docs/adr/0018-*`.
- Ya validado bajo Deno 2.9.6 (spike S6): Tailwind vía `@tailwindcss/vite`, `svelte-check`,
  Vitest (exige `resolve.conditions: ['browser']`) y Playwright, incluido el runner.
- **No** funciona `@testing-library/svelte`: usar `mount()` de Svelte.

### Comandos canónicos

| Quiero | Comando |
|---|---|
| Sincronizar el entorno Python | `uv sync` |
| Añadir dependencia | `uv add <paquete>` · `uv add --dev <paquete>` |
| Levantar Postgres | `docker compose up -d postgres` |
| Backend en desarrollo | `uv run uvicorn app.main:app --reload` |
| Migraciones | `uv run alembic upgrade head` |
| Sembrar datos canónicos | `uv run python -m app.seed` |
| Tests backend | `uv run pytest` |
| Formato + lint Python | `uv run ruff format .` · `uv run ruff check --fix .` |
| Dev del frontend | `deno task dev` |
| Build del frontend | `deno task build` |
| Typecheck del frontend | `deno check` |
| Formato + lint del frontend | `deno fmt` · `deno lint` |
| Tests del frontend | `deno test` |
| Regenerar el cliente API | `deno task openapi` |

El `Makefile` es solo un envoltorio fino sobre `uv run` y `deno task`. Si añades un target,
que delegue en ellos: no dupliques comandos.

---

## 3. Invariantes de arquitectura (no negociables)

1. **La costura única.** `langgraph` y `langchain` se importan **solo** dentro de
   `backend/app/agent/`. Los routers y el resto del backend no saben que existe LangGraph.
   Lo verifica `import-linter` en CI — si falla, no lo silencies, corrige el import.
2. **`agent/service.py` es la API pública del núcleo.** Devuelve **DTOs de dominio**, nunca
   `BaseMessage` ni tipos de la librería.
3. **No se escribe SQL propio para conversación ni memoria.** El historial vive en el
   checkpointer y los hechos en el `Store`. Prohibido crear tablas de mensajes o sesiones.
4. **`threads` es cache de UI, no fuente de verdad.** `message_count`, `last_preview` y
   `title` los mantiene el servicio; si discrepan del checkpointer, manda el checkpointer.
5. **OpenAPI es el contrato.** El cliente TypeScript se **regenera**; nunca se escribe un
   `fetch` a mano ni se edita el cliente generado.
6. **Un solo `<Chat>` y tres skins.** Las skins solo cambian la cáscara visual. Prohibido
   ramificar comportamiento por canal.
7. **i18n en 6 idiomas** (es, en, fr, pt, ko, zh) con paridad de claves. Una clave nueva se
   añade a los seis o no se añade.

---

## 4. Contrato de memoria y prompt (D7)

Este es el punto donde más fácil es romper algo sin darse cuenta.

- **La memoria es nativa.** No existe interruptor de configuración: todo agente la tiene.
- **Namespace:** `("agent", str(agent_id), "user", str(user_id))`. Las etiquetas del `Store`
  de LangGraph **deben ser cadenas**: con enteros lanza `InvalidNamespaceError` (spike S2).
  Nunca mezcles memorias entre usuarios.
- **Orden canónico del prompt:**
  ```
  [system][historial][memoria][mensaje nuevo]
  ```
- **La memoria se inyecta al final y de forma transitoria.** Se arma al construir el prompt y
  **no se persiste** en el estado del hilo. Persistirla la repetiría una vez por turno,
  inflaría el prompt y mostraría recuerdos obsoletos.
- **Nada volátil al principio del prompt.** Ni hora, ni ids de request, ni contadores: eso
  invalida la caché completa en cada turno y multiplica el costo.
- **Los hechos se escriben en orden de inserción.** No los reordenes ni los reescribas al
  persistir: rompe la caché.
- **Techo de inyección:** `0.4 × contexto_del_modelo`, calculado en runtime. No hardcodees
  un número.
- **Cola de consolidación:** tabla en Postgres con `SELECT ... FOR UPDATE SKIP LOCKED`,
  encolada **en la misma transacción que el turno**. `N = 1` (consolidación por turno) es
  palanca de configuración, no lógica adaptativa.
- **`threads.last_consolidated_at`** delimita la ventana e impide reprocesar. No la elimines.
- **Deduplicación obligatoria** antes de persistir hechos nuevos.

---

## 5. Invariantes de seguridad

- `SECRET_KEY` es **obligatoria y sin valor por defecto**. Nada de fallbacks "para
  desarrollo".
- **Ningún endpoint mutador sin autorización.** Cada endpoint declara su política
  (`require_user` / `require_admin` / pertenencia del recurso) y tiene test.
- **Subidas de archivo:** sin SVG, con límite de tamaño y validación de tipo. Se sirven
  desde un endpoint con `Content-Disposition`, nunca desde un directorio estático.
- **Nunca `debug=True`** ni recarga automática en configuración de producción.
- **Nunca commitees `.env`** ni secretos. Solo `.env.example`, con valores de ejemplo.
- Contraseñas con **Argon2**.
- Errores con forma estable `{error, code, detail}`.

---

## 6. Testing

- **El núcleo se testea sin I/O real:** `FakeLLM`, `InMemorySaver`, `InMemoryStore` y cola
  falsa. Si un test del núcleo necesita red o base de datos, el código está mal estructurado.
- **Contrato:** snapshot de OpenAPI versionado; si cambia y el snapshot no se actualiza, el
  test falla a propósito.
- **Autorización:** test paramétrico 401 / 403 / 404 por endpoint.
- **Prompt:** tests *golden* del string resultante, y test de que el prefijo
  `[system][historial]` no cambia entre turnos consecutivos.
- No borres ni comentes un test para pasar CI. Si un test está mal, arréglalo o repórtalo.

---

## 7. Convenciones

- **Documentación y prosa en español; identificadores, nombres de archivo y código en
  inglés** (como hace la propuesta: `knowledge_sources`, no `fuentes_conocimiento`).
- Comentarios solo cuando explican *por qué*, no *qué*.
- `ruff format` para Python y `deno fmt` para el frontend antes de dar algo por terminado.
- Commits y ramas: no se hacen salvo que el usuario lo pida explícitamente.

---

## 8. Qué NO hacer

- No instalar dependencias con `pip`, `npm`, `yarn`, `pnpm`, `poetry` ni `conda`.
- No crear tablas de mensajes, sesiones o memoria propias.
- No importar `langgraph`/`langchain` fuera de `app/agent/`.
- No tocar `../theythink-ai` (solo lectura).
- No cambiar el orden del prompt ni persistir la memoria inyectada.
- No escribir `fetch` a mano contra el backend: usa el cliente generado.
- No añadir selección, recorte o compactación de memoria por iniciativa propia: eso está
  gobernado por D7 y su métrica.
- No añadir comportamiento por canal en las skins.
- No introducir secretos, endpoints mutadores sin autorización, ni SVG en avatares.
- No dejar una fase "casi lista": el gate de la siguiente fase es el DoD de la anterior.

---

## 9. Antes de dar algo por terminado

1. ¿Respeta las decisiones de la propuesta §3 y §14?
2. ¿Tiene tests (núcleo sin I/O, contrato de endpoints)?
3. ¿Pasa `uv run ruff check .`, `uv run pytest`, `deno check`, `deno lint` y `deno test`?
4. ¿`import-linter` sigue verde?
5. ¿El snapshot de OpenAPI y el cliente generado están actualizados?
6. ¿Actualizaste el plan §0 (registro de estado) y los ADR que correspondan?

Si algo de esto no se puede cumplir, dilo explícitamente en el resumen final en vez de
darlo por bueno.