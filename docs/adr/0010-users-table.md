# 0010 — Una sola tabla `users` y registro público

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §6.1, §14 (D6, D13); plan §4 (hueco 1), §5 Fases 1 y 3

## Contexto
La propuesta asumía usuarios finales por canal, pero el sistema actual no los tiene: `usuarios` es la tabla de staff. Había que decidir si existen identidades anónimas o por canal, y cómo se dan de alta las cuentas.

## Decisión
Una sola tabla **`users`** (`username` UNIQUE, `email` UNIQUE, `password_hash` con Argon2, `role`, `created_at`), con los roles `admin` y `usuario`. Sin usuarios anónimos ni identidades por canal: `threads.user_id` y el namespace de memoria apuntan a `users.id`. El alta es por **registro público**: el primer `admin` se siembra en Fase 1 y el resto de cuentas nacen con `role = 'usuario'`.

## Alternativas consideradas
- **Identidades por canal o usuarios anónimos:** descartado; WhatsApp y Telegram son skins del mismo frontend autenticado (D3), así que no aportan identidad propia.

## Notas de migración
- La tabla `usuarios` actual no tiene `email`: se sintetiza en el migrador (`--admin-email`).
- Usa el hash de Werkzeug (`scrypt`, vía `generate_password_hash`): se re-hashea a Argon2 en el primer login exitoso, con `werkzeug` como dependencia **solo de migración**.

## Consecuencias
- Contrapartida aceptada (D6): dos personas que compartan una cuenta comparten memoria; se cubre con test de aislamiento.
- Fase 3: endpoint de registro con unicidad de `username` y `email` y política de contraseña. Fase 6: rate limiting, verificación de email o captcha si el abuso lo exige.
- Obliga a: ningún endpoint mutador sin autorización (`require_user` / `require_admin` / pertenencia del recurso).
