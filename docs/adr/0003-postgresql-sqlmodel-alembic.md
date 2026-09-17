# 0003 — PostgreSQL con SQLModel y Alembic

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §3 (A2), §4, §6; plan §5 Fase 1

## Contexto
El proyecto actual usa SQLite, de escritor único. Con FastAPI async eso es una incongruencia: las escrituras se serializan y el motor no soporta el patrón de cola con `SELECT ... FOR UPDATE SKIP LOCKED` del que depende D14.

## Decisión
Una sola base **PostgreSQL**, con **SQLModel + Alembic** para las entidades de dominio y `asyncpg` como driver.

## Alternativas consideradas
- **SQLite + `aiosqlite`:** descartado; su semántica de escritor único no da concurrencia real.
- **Un motor por consumidor** (relacional + cola): descartado; la cola vive en Postgres (D14).

## Consecuencias
- Concurrencia real y un solo motor coherente para dominio, checkpointer y cola.
- Dos autoridades de migración en la misma BD (Alembic y `setup()` de LangGraph): hay que documentar el orden, excluir las tablas de la librería del autogenerate y evitar que un `downgrade` las borre (plan §4, hueco 6).
- Obliga a: Postgres en `docker-compose` para dev, esquema efímero por sesión en tests (D11) y backups en Fase 6.
- Cuesta un servicio que operar en lugar de un archivo local.
