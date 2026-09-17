"""Engine async de base de datos, sesión y comprobación de disponibilidad.

El engine se construye de forma perezosa: importar este módulo no abre conexiones ni exige
que la configuración esté completa.
"""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """Engine async compartido por todo el proceso."""
    settings = get_settings()
    return create_async_engine(str(settings.database_url), pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Fábrica de sesiones ligada al engine compartido."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependencia de FastAPI: una sesión por request."""
    async with get_sessionmaker()() as session:
        yield session


async def ping_database() -> bool:
    """Comprueba que la base responde. Lo usa `/readyz`."""
    try:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return False
    return True
