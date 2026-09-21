"""Configuracion compartida de los tests.

Los tests del **nucleo** no tocan red ni base de datos: usan dobles (ver AGENTS.md §6).
Los tests de **dominio, migraciones y contrato** si necesitan Postgres: D11 (ADR `0016`)
define un esquema efimero por sesion que se crea y destruye aqui.

Aislamiento: el fixture `session` abre una transaccion externa y la revierte al terminar,
de modo que cada test parte de un esquema vacio sin pagar la creacion de tablas por test.
"""

import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-with-at-least-32-characters")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://theyrethink:theyrethink@localhost:5432/theyrethink",
)

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlmodel import SQLModel

import app.models  # noqa: F401  (registra el metadata de dominio)
from app.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
async def ephemeral_schema() -> AsyncIterator[str]:
    """Crea un esquema de Postgres efimero para toda la sesion de tests (D11)."""
    admin_engine = create_async_engine(
        str(get_settings().database_url), isolation_level="AUTOCOMMIT"
    )
    schema = f"test_{uuid4().hex[:12]}"
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        yield schema
    finally:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin_engine.dispose()


@pytest.fixture(scope="session")
async def db_engine(ephemeral_schema: str) -> AsyncIterator[AsyncEngine]:
    """Engine apuntado al esquema efimero, con el esquema de dominio ya creado."""
    engine = create_async_engine(
        str(get_settings().database_url),
        connect_args={"server_settings": {"search_path": ephemeral_schema}},
    )
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Sesion envuelta en una transaccion que se revierte al terminar el test."""
    async with db_engine.connect() as connection:
        transaction = await connection.begin()
        async_session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield async_session
        finally:
            await async_session.close()
            await transaction.rollback()
