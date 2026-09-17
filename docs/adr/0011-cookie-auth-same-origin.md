# 0011 — Sesión por cookie httpOnly en el mismo origen

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §4, §14 (D2, D4); plan §5 Fases 3 y 6

## Contexto
El proyecto actual no tiene autorización real y depende de fallbacks. Hay que elegir el mecanismo de sesión y la topología de despliegue, sabiendo que un JWT no es revocable sin infraestructura extra.

## Decisión
Autenticación por **cookie de sesión httpOnly con store en Postgres** (revocable), y despliegue en **el mismo origen**: FastAPI sirve `/api/v1` y el frontend, así que **no hay CORS**.

## Alternativas consideradas
- **JWT:** descartado para v1; no es revocable sin lista de revocación.
- **Orígenes separados con CORS:** descartado; complica cookies y CSRF sin aportar nada aquí.

## Consecuencias
- Habilita logout y revocación de sesión; con D4 quedan simplificados cookies y CSRF.
- Obliga a: flags `HttpOnly` / `Secure` / `SameSite` y anti-fijación de sesión en login (Fase 6), y a verificación de pertenencia del recurso por endpoint (un hilo solo lo ve su dueño).
- Fase 6 debe endurecer explícitamente lo que D4 deja "innecesario por diseño".
- Cuesta acoplar el despliegue a un único origen: el backend también sirve los estáticos del frontend.
