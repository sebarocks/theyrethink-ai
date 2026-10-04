"""Límite de peticiones por ventana fija contada en Postgres (D23, ADR `0026`).

El contador vive en la base y no en memoria del proceso: con varios workers (D22) un límite
local se multiplicaría por el número de procesos. La tabla es **operativa**, no de dominio.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RateLimitHit

__all__ = ["RateLimitExceeded", "enforce_rate_limit", "window_start_for"]


class RateLimitExceeded(Exception):
    """Se superó el número de peticiones permitido dentro de la ventana."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"límite de peticiones superado; reintenta en {retry_after}s")
        self.retry_after = max(retry_after, 1)


def window_start_for(now: dt.datetime, window_seconds: int) -> int:
    """Inicio (epoch, segundos) de la ventana fija que contiene `now`."""
    return int(now.timestamp()) // window_seconds * window_seconds


async def enforce_rate_limit(
    session: AsyncSession,
    *,
    scope: str,
    key: str,
    limit: int,
    window_seconds: int,
    now: dt.datetime | None = None,
) -> int:
    """Cuenta la petición y lanza `RateLimitExceeded` si supera `limit`.

    El incremento se **confirma** antes de devolver. Si no, una petición que termina en error
    (un login fallido revierte la transacción del request) borraría el contador y el límite no
    frenaría nada. Devuelve el número de peticiones contadas en la ventana actual.
    """
    if limit <= 0:
        return 0

    moment = now or dt.datetime.now(dt.UTC)
    start = window_start_for(moment, window_seconds)

    statement = (
        pg_insert(RateLimitHit)
        .values(scope=scope, key=key, window_start=start, count=1)
        .on_conflict_do_update(
            index_elements=[RateLimitHit.scope, RateLimitHit.key, RateLimitHit.window_start],
            set_={"count": RateLimitHit.count + 1},
        )
        .returning(RateLimitHit.count)
    )
    count = (await session.execute(statement)).scalar_one()

    # Purga perezosa: no hace falta un proceso de limpieza aparte.
    await session.execute(
        delete(RateLimitHit).where(
            RateLimitHit.scope == scope,
            RateLimitHit.window_start < start - window_seconds,
        )
    )
    await session.commit()

    if count > limit:
        raise RateLimitExceeded(retry_after=start + window_seconds - int(moment.timestamp()))
    return count
