"""Test de migraciones (D11): `alembic upgrade head` y ausencia de drift con los modelos.

Se ejecuta en subproceso porque `alembic/env.py` crea su propio event loop
(`asyncio.run`), incompatible con el loop de pytest-asyncio.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
LIBRARY_TABLES = ("checkpoints", "checkpoint_blobs", "store", "store_migrations")


def _engine(schema: str | None = None) -> AsyncEngine:
    connect_args = {"server_settings": {"search_path": schema}} if schema else {}
    return create_async_engine(
        str(get_settings().database_url), isolation_level="AUTOCOMMIT", connect_args=connect_args
    )


async def _execute(schema: str | None, *statements: str) -> None:
    engine = _engine(schema)
    async with engine.begin() as connection:
        for statement in statements:
            await connection.execute(text(statement))
    await engine.dispose()


async def _table_names(schema: str) -> set[str]:
    engine = _engine(schema)

    def _list(sync_connection) -> set[str]:
        return set(inspect(sync_connection).get_table_names())

    async with engine.connect() as connection:
        tables = await connection.run_sync(_list)
    await engine.dispose()
    return tables


def _alembic(*args: str, schema: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DB_SCHEMA": schema}
    return subprocess.run(
        (sys.executable, "-m", "alembic", *args),
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_migration_head_applies_and_has_no_drift() -> None:
    schema = f"mig_{uuid4().hex[:12]}"
    asyncio.run(_execute(None, f'CREATE SCHEMA "{schema}"'))
    try:
        upgrade = _alembic("upgrade", "head", schema=schema)
        assert upgrade.returncode == 0, upgrade.stderr

        check = _alembic("check", schema=schema)
        assert check.returncode == 0, check.stdout + check.stderr
    finally:
        asyncio.run(_execute(None, f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def test_alembic_ignores_langgraph_tables() -> None:
    """Alembic no crea ni borra las tablas de la libreria (spike S2, include_object)."""
    schema = f"mig_{uuid4().hex[:12]}"
    drop = f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'
    asyncio.run(_execute(None, f'CREATE SCHEMA "{schema}"'))
    try:
        # Centinelas: tablas de la libreria ya presentes antes de migrar.
        asyncio.run(
            _execute(
                schema,
                *[f"CREATE TABLE {table} (id integer)" for table in LIBRARY_TABLES],
            )
        )

        assert _alembic("upgrade", "head", schema=schema).returncode == 0
        assert _alembic("downgrade", "base", schema=schema).returncode == 0

        remaining = asyncio.run(_table_names(schema))
        assert set(LIBRARY_TABLES) <= remaining
        assert "users" not in remaining and "agents" not in remaining
    finally:
        asyncio.run(_execute(None, drop))
