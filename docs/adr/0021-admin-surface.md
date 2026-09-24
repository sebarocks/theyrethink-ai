# 0021 — Superficie de administración

- **Estado:** aceptada
- **Fecha:** 2026-09-24
- **Fuente:** propuesta §8, §9.1, §9.2, §14 (D17, D18, D19); plan §3, §5 Fase 4

## Contexto

El dashboard `/admin/*` (propuesta §9.2) necesita, además de lo ya expuesto (roles y fuentes
con CRUD, agentes con alta y avatar), tres capacidades que la Fase 3 no cubría:

1. **Gestionar usuarios** (D17): el registro público (D13) solo da de alta cuentas con rol
   `usuario`; no hay forma de listarlas, editarlas, cambiarles el rol ni borrarlas.
2. **Auditar conversaciones** (D18): `threads` solo expone las del usuario autenticado; el
   dashboard necesita ver todas y leer cualquier transcript.
3. **Editar el perfil propio** (D19): no había endpoint para cambiarse el nombre, el correo o
   la contraseña.

Además, el CRUD de agentes de la propuesta (§9.1) estaba incompleto: existían alta, avatar,
consulta y asociación de fuentes, pero no edición ni borrado.

## Decisión

**D17 — Router `users`, solo `require_admin`.** `GET`/`POST /api/v1/users`,
`PATCH`/`DELETE /api/v1/users/{user_id}`. La contraseña se hashea con Argon2 y nunca se
expone. Salvaguardas: un admin no puede eliminarse ni quitarse el rol `admin` (409
`cannot_modify_self`); unicidad de `username`/`email` ⇒ 409.

**D18 — Router `admin`, solo `require_admin`.** `GET /api/v1/admin/threads` lista **todas**
las conversaciones (con `agent_name` y `username`, filtro opcional `?agent_id=`) y
`GET /api/v1/admin/threads/{id}/messages` lee cualquier transcript. La lectura se hace por
`agent/service.py` (D16); el router **no** conoce el checkpointer.

**D19 — `PATCH /api/v1/auth/me`, solo `CurrentUser`.** Actualiza `username` y/o `email` y,
opcionalmente, la contraseña. Cambiar la contraseña exige `current_password` y se verifica
con `verify_password`; la nueva se hashea con Argon2. Unicidad ⇒ 409. No permite cambiar el
propio rol.

**CRUD de agentes completado.** Se añaden `PATCH /api/v1/agents/{id}` (nombre, perfil,
`role_key`, identidad personalizada) y `DELETE /api/v1/agents/{id}` (borra también el avatar
del disco), ambos `require_admin`. Completan el CRUD ya especificado; no introducen una
decisión nueva.

**Lectura de asociaciones agente↔fuente.** Se añade `GET /api/v1/agents/{id}/sources`
(lectura de usuario) para que el dashboard pueda mostrar y editar qué fuentes tiene asociadas
un agente sin escribir SQL propio. La escritura sigue siendo `PUT`/`DELETE`
`require_admin`.

## Alternativas consideradas

- **Extender `/threads` con un parámetro `all=true` para admin:** descartada; mezcla dos
  políticas de autorización (pertenencia vs. admin) en el mismo endpoint y hace fácil olvidar
  el chequeo.
- **Leer usuarios/transcripciones desde el frontend agregando los endpoints existentes:**
  imposible para usuarios (no hay endpoint) y para conversaciones ajenas (el ownership lo
  impide por diseño).
- **Cambiar la contraseña sin exigir la actual:** descartada; el perfil se edita con sesión,
  pero pedir la contraseña actual es la barrera mínima ante una sesión robada.

## Consecuencias

- Cambia el contrato OpenAPI: se actualiza `docs/openapi.json` y se regenera el cliente TS.
- Ningún endpoint mutador nuevo queda sin autorización; el test paramétrico 401/403/404 se
  extiende a `users` y `admin`.
- El borrado de usuario cae en cascada (`ON DELETE CASCADE`) sobre sus `sessions`, `threads`,
  `consolidation_jobs`; **no** toca el `Store` de memoria (coherente con D10: olvidar memoria
  es un endpoint aparte, aún no implementado).
- El router `admin` es de solo lectura salvo la baja de usuario: no introduce tablas nuevas ni
  migraciones.
