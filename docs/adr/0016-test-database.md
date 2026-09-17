# 0016 — Base de datos de test: esquema efímero por sesión

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §14 (D11); plan §5 Fases 1 y 2

## Contexto
Los tests de modelos, migraciones y contrato necesitan una BD real, pero compartir un esquema sucio entre corridas produce fallos espurios y estados imposibles de reproducir.

## Decisión
Cada sesión de tests crea un **esquema efímero** sobre el **Postgres de `docker-compose`** y lo destruye al terminar.

## Alternativas consideradas
- **Base embebida (SQLite) o mocks de sesión:** descartado; no ejercitaría el motor real ni las particularidades de Postgres y `asyncpg` de las que ya depende el diseño (A2).
- **Esquema compartido persistente:** descartado; arrastra estado entre corridas.

## Consecuencias
- Los tests del núcleo siguen **sin I/O real** (`FakeLLM`, `InMemorySaver`, `InMemoryStore`, cola falsa); esta BD es para dominio, migraciones y contrato.
- La suite de integración depende de que el Postgres esté arriba, en local y en CI.
- Cuesta tiempo de creación y destrucción del esquema por sesión.
