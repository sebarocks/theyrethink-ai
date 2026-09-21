"""Entorno de migraciones Alembic (async, con `asyncpg`).

Dos autoridades de migracion comparten la base (ver `alembic/README` y el spike S2):

1. `setup()` de LangGraph crea `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`,
   `checkpoint_migrations`, `store` y `store_migrations`.
2. Alembic gestiona solo el esquema **de dominio** (`app/models/domain.py`).

Por eso esas seis tablas se excluyen del autogenerate: si no, Alembic las veria como
"faltantes" (o peor, un `downgrade` las borraria).

La URL no vive en `alembic.ini`: se toma de `app.config.Settings`. Si se define la variable
de entorno `DB_SCHEMA`, el engine fija `search_path` a ese esquema; lo usan los tests para
levantar un esquema efimero por sesion (D11) sin tocar el resto de la base.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

import app.models  # noqa: F401  (importar el paquete registra el metadata)
from alembic import context
from app.config import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

# Tablas de LangGraph: no son nuestras y no se migran con Alembic (spike S2).
LIBRARY_TABLES = frozenset(
    {
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
        "checkpoint_migrations",
        "store",
        "store_migrations",
    }
)


def include_object(
    obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
) -> bool:
    """Excluye del autogenerate las tablas gestionadas por LangGraph."""
    if type_ == "table" and name in LIBRARY_TABLES:
        return False
    return True


def _database_url() -> str:
    return str(get_settings().database_url)


def _connect_args() -> dict[str, object]:
    schema = os.environ.get("DB_SCHEMA")
    if not schema:
        return {}
    return {"server_settings": {"search_path": schema}}


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(
        _database_url(), poolclass=pool.NullPool, connect_args=_connect_args()
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
