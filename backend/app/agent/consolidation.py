"""Cola de consolidacion de memoria (D7/D14).

Tabla en Postgres con `SELECT ... FOR UPDATE SKIP LOCKED`. La ventaja decisiva de D14 es que
**el encolado ocurre en la misma transaccion que el turno**: no hay forma de perderlo ni
duplicarlo, y no se suma un servicio mas que operar.

La cola se abstrae tras `ConsolidationQueue` para que el nucleo se testee con una cola falsa
(AGENTS.md §6).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.dto import ConsolidationJobDTO
from app.agent.observability import log_event
from app.models import ConsolidationJob

__all__ = [
    "ConsolidationQueue",
    "ConsolidationWorker",
    "FakeConsolidationQueue",
    "PostgresConsolidationQueue",
]


class ConsolidationQueue(Protocol):
    """Contrato de la cola de consolidacion."""

    async def enqueue(
        self, session: AsyncSession, *, thread_id: int, agent_id: int, user_id: int
    ) -> None:
        """Encola un trabajo **en la transaccion del llamador** (no hace commit)."""
        ...

    async def claim(self, *, limit: int = 1) -> list[ConsolidationJobDTO]:
        """Reclama hasta `limit` trabajos pendientes, excluyendo los ya reclamados."""
        ...

    async def complete(self, job_id: int) -> None:
        """Marca un trabajo como procesado (lo elimina)."""
        ...

    async def fail(self, job_id: int, error: str) -> None:
        """Registra el fallo y deja el trabajo reintentable."""
        ...


class PostgresConsolidationQueue:
    """Implementacion sobre la tabla `consolidation_jobs` (D14)."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], *, max_attempts: int = 3):
        self._sessionmaker = sessionmaker
        self._max_attempts = max_attempts

    async def enqueue(
        self, session: AsyncSession, *, thread_id: int, agent_id: int, user_id: int
    ) -> None:
        session.add(ConsolidationJob(thread_id=thread_id, agent_id=agent_id, user_id=user_id))
        await session.flush()

    async def claim(self, *, limit: int = 1) -> list[ConsolidationJobDTO]:
        async with self._sessionmaker() as session:
            async with session.begin():
                rows = (
                    (
                        await session.execute(
                            select(ConsolidationJob)
                            .where(ConsolidationJob.attempts < self._max_attempts)
                            .order_by(ConsolidationJob.created_at)
                            .with_for_update(skip_locked=True)
                            .limit(limit)
                        )
                    )
                    .scalars()
                    .all()
                )
                now = dt.datetime.now(dt.UTC)
                for row in rows:
                    row.claimed_at = now
                    row.attempts += 1
                return [
                    ConsolidationJobDTO(
                        id=row.id,
                        thread_id=row.thread_id,
                        agent_id=row.agent_id,
                        user_id=row.user_id,
                        created_at=row.created_at,
                        attempts=row.attempts,
                    )
                    for row in rows
                ]

    async def complete(self, job_id: int) -> None:
        async with self._sessionmaker() as session:
            await session.execute(delete(ConsolidationJob).where(ConsolidationJob.id == job_id))
            await session.commit()

    async def fail(self, job_id: int, error: str) -> None:
        async with self._sessionmaker() as session:
            job = await session.get(ConsolidationJob, job_id)
            if job is not None:
                job.last_error = error[:2000]
                job.claimed_at = None
                await session.commit()


class FakeConsolidationQueue:
    """Cola en memoria para los tests del nucleo (AGENTS.md §6)."""

    def __init__(self) -> None:
        self.jobs: list[ConsolidationJobDTO] = []
        self.completed: list[int] = []
        self.failed: list[tuple[int, str]] = []
        self._next_id = 1

    async def enqueue(
        self, session: AsyncSession | None, *, thread_id: int, agent_id: int, user_id: int
    ) -> None:
        self.jobs.append(
            ConsolidationJobDTO(
                id=self._next_id,
                thread_id=thread_id,
                agent_id=agent_id,
                user_id=user_id,
                created_at=dt.datetime.now(dt.UTC),
            )
        )
        self._next_id += 1

    async def claim(self, *, limit: int = 1) -> list[ConsolidationJobDTO]:
        claimed = self.jobs[:limit]
        self.jobs = self.jobs[limit:]
        return claimed

    async def complete(self, job_id: int) -> None:
        self.completed.append(job_id)

    async def fail(self, job_id: int, error: str) -> None:
        self.failed.append((job_id, error))


class ConsolidationWorker:
    """Consume la cola y delega en `consolidate` (el servicio).

    `N=1` (D7): un trabajo por turno. El worker no conoce el grafo; solo reclama, delega y
    cierra el trabajo, de modo que se testea con una cola falsa y un `consolidate` falso.
    """

    def __init__(
        self,
        *,
        queue: ConsolidationQueue,
        consolidate: Callable[[ConsolidationJobDTO], Awaitable[object]],
        interval_seconds: float = 1.0,
        batch_size: int = 1,
    ):
        self._queue = queue
        self._consolidate = consolidate
        self._interval = interval_seconds
        self._batch_size = batch_size
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def run_once(self) -> int:
        """Procesa un lote. Devuelve cuantos trabajos se atendieron."""
        jobs = await self._queue.claim(limit=self._batch_size)
        for job in jobs:
            try:
                await self._consolidate(job)
            except Exception as error:  # noqa: BLE001 - un fallo no debe tumbar el worker
                log_event(
                    "consolidation.failed",
                    level=logging.ERROR,
                    thread_id=job.thread_id,
                    agent_id=job.agent_id,
                    user_id=job.user_id,
                    error=str(error),
                )
                await self._queue.fail(job.id, str(error))
            else:
                await self._queue.complete(job.id)
        return len(jobs)

    async def run_forever(self) -> None:
        """Bucle del worker hasta que se pida parar."""
        while not self._stop.is_set():
            processed = await self.run_once()
            if processed == 0:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
                except TimeoutError:
                    pass

    def start(self) -> asyncio.Task[None]:
        """Lanza el bucle como tarea de fondo (lo usa el `lifespan`)."""
        self._task = asyncio.create_task(self.run_forever())
        return self._task

    async def stop(self) -> None:
        """Pide parar y espera a que la tarea termine."""
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None
