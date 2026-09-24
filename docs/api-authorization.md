# Matriz de autorización de la API

La API usa sesiones por cookie `httpOnly` y mismo origen. Todas las rutas `/api/v1`, salvo
`/auth/register` y `/auth/login`, requieren una sesión válida.

| Recurso | Lectura | Mutación | Regla de recurso |
|---|---|---|---|
| `auth/register` | pública | pública | Crea siempre `usuario` |
| `auth/login` | pública | pública | Crea una sesión revocable |
| `auth/me` | usuario | usuario | Solo la sesión actual; `PATCH` edita el perfil propio (D19) |
| `auth/logout` | usuario | usuario | Revoca las sesiones del usuario |
| `agents` | usuario | admin | Un agente inexistente devuelve `404` |
| `agents/{id}` escritura | — | admin | `PATCH`/`DELETE`; nombre duplicado ⇒ `409` |
| `roles` | usuario | admin | Un rol inexistente devuelve `404` |
| `sources` | usuario | admin | Una fuente inexistente devuelve `404` |
| asociaciones agente-fuente | usuario | admin | Agente/fuente inexistente devuelve `404`; `GET /agents/{id}/sources` lee, `PUT`/`DELETE` mutan |
| `users` | admin | admin | Solo administradores; no puede autoeliminarse ni auto-degradarse (`409`) |
| `admin/threads` | admin | — | Lista todas las conversaciones; filtro `?agent_id=` |
| `admin/threads/{id}/messages` | admin | — | Transcript de cualquier hilo (D16/D18) |
| `threads` | propietario | propietario | Un hilo ajeno se oculta como `404` |
| `chat` | propietario | propietario | Un hilo ajeno se oculta como `404` |
| `agents/{id}/avatar` lectura | usuario | — | Agente/avatar inexistente devuelve `404` |
| `agents/{id}/avatar` escritura | — | admin | Agente inexistente devuelve `404` |

## Respuestas de autorización

- Sin sesión: `401` con `code = authentication_required` o `invalid_session`.
- Sesión válida sin privilegios: `403` con `code = admin_required`.
- Recurso inexistente o ajeno: `404` con un código específico del recurso.
- Payload inválido: `422` con `code = invalid_request`.
- Conflicto de unicidad o asociación duplicada: `409` con un código específico.

La matriz se verifica mediante `backend/tests/test_api_contract.py` y los tests de cada router.
