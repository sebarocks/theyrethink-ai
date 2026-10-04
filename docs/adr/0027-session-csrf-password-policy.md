# 0027 — Cookie configurable, anti-fijación, CSRF y política de contraseña

- **Estado:** aceptada
- **Fecha:** 2026-10-02
- **Fuente:** propuesta §11 y §14 (D24); ADR `0011`, `0026`

## Contexto

La propuesta §11 pide endurecer sesión y contraseñas antes del corte. Al revisar el código de la
Fase 3 aparecían cuatro huecos:

1. La cookie de sesión fijaba `secure=True` en el código, sin forma de desactivarlo en un
   desarrollo servido por HTTP.
2. El login no revocaba nada al cambiar la contraseña, así que una sesión robada sobrevivía al
   cambio de credenciales.
3. No había ninguna comprobación de `Origin`, solo `SameSite=Lax`.
4. La única regla de contraseña era `min_length=8`, sin relación con la identidad del usuario.

## Decisión

1. **Cookie configurable.** `httpOnly` y `SameSite` se mantienen explícitos; `Secure`
   (`SESSION_COOKIE_SECURE`, por defecto `true`), `SESSION_COOKIE_SAMESITE` (`lax` por defecto),
   `SESSION_COOKIE_DOMAIN` y `SESSION_DAYS` salen de configuración. El valor por defecto es el
   seguro; relajarlo es una decisión explícita de desarrollo, nunca el comportamiento implícito.
2. **Anti-fijación.** El token de sesión es CSPRNG (`secrets.token_urlsafe(32)`), se emite solo
   tras autenticar y se rota en cada login. Al cambiar la contraseña (`PATCH /auth/me`) se
   revocan **las demás sesiones** del usuario y se conserva la actual. El logout ya revocaba
   todas las activas.
3. **CSRF por `Origin`.** Sobre `SameSite=Lax`, un middleware comprueba `Origin` (o, en su
   defecto, `Referer`) contra una allowlist de orígenes (`ALLOWED_ORIGINS`) en métodos no
   seguros (`POST`, `PUT`, `PATCH`, `DELETE`). Si la cabecera no viene —clientes no navegador,
   tests, `curl`— se permite y se registra, porque no hay nada que comparar; la defensa real
   para un navegador es la cabecera.
4. **Política de contraseña.**
   - Longitud mínima configurable (`PASSWORD_MIN_LENGTH`, por defecto 8, el actual, para no
     invalidar cuentas existentes) y máxima 128.
   - Se rechaza si la contraseña coincide con el `username` o con la parte local del `email`.
   - Argon2 con los parámetros por defecto de `argon2-cffi` (RFC 9106), documentados como
     deliberados: fijarlos a mano congelaría el coste de CPU sin medirlo. `needs_rehash` ya
     permite subirlos en el futuro.
5. **Intentos:** el límite de `/auth/login` y `/auth/register` es D23 (ADR `0026`).

## Alternativas consideradas

- **Doble cookie CSRF (patrón *double-submit*).** Más robusto frente a orígenes mal
  configurados, pero exige coordinar el token con el cliente generado y añade estado en el
  frontend. Con el mismo origen (D4) y `SameSite=Lax`, la comprobación de `Origin` cubre el caso
  real. Descartada de momento.
- **Lista de contraseñas filtradas (p. ej. HIBP).** Mejor que una regla de composición, pero
  implica una dependencia y tráfico de red en el alta. Se deja para Fase 7 si el abuso lo pide.
- **Reglas de composición (mayúsculas, símbolos).** La evidencia actual favorece longitud sobre
  composición; se opta por longitud mínima configurable + no reutilizar la identidad.
- **Invalidar todas las sesiones al cambiar la contraseña.** Más agresivo (expulsa también al
  dispositivo que cambia la contraseña), peor experiencia sin ganancia clara aquí.

## Consecuencias

- El desarrollo por HTTP exige `SESSION_COOKIE_SECURE=false` de forma explícita.
- Cambiar la contraseña cierra sesión en el resto de dispositivos; hay test que lo verifica.
- Con `ALLOWED_ORIGINS` vacío el middleware solo acepta peticiones sin `Origin` o con el mismo
  origen de la petición, que es el caso de D4.
- Un atacante que consiga ejecutar código en el mismo origen (XSS) sigue pudiendo actuar; esto no
  sustituye a una CSP, que queda anotada para el endurecimiento posterior.
