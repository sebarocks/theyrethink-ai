"""Tests de la cola de consolidacion y su worker (D7/D14)."""

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agent.consolidation import (
    ConsolidationWorker,
    FakeConsolidationQueue,
    PostgresConsolidationQueue,
)
from app.agent.dto import ConsolidationJobDTO
from app.models import Agent, Thread, User


async def test_worker_completes_successful_job() -> None:
    queue = FakeConsolidationQueue()
    processed: list[int] = []

    async def consolidate(job: ConsolidationJobDTO) -> None:
        processed.append(job.thread_id)

    await queue.enqueue(None, thread_id=10, agent_id=1, user_id=1)
    worker = ConsolidationWorker(queue=queue, consolidate=consolidate)

    assert await worker.run_once() == 1
    assert processed == [10]
    assert queue.completed == [1]
    assert queue.failed == []


async def test_worker_records_failure_and_keeps_going() -> None:
    queue = FakeConsolidationQueue()
    seen: list[int] = []

    async def consolidate(job: ConsolidationJobDTO) -> None:
        seen.append(job.thread_id)
        if job.thread_id == 10:
            raise RuntimeError("boom")

    await queue.enqueue(None, thread_id=10, agent_id=1, user_id=1)
    await queue.enqueue(None, thread_id=11, agent_id=1, user_id=1)
    worker = ConsolidationWorker(queue=queue, consolidate=consolidate, batch_size=2)

    assert await worker.run_once() == 2
    assert seen == [10, 11]
    assert queue.completed == [2]
    assert queue.failed == [(1, "boom")]


async def _seed_thread(sessionmaker: async_sessionmaker) -> int:
    async with sessionmaker() as session:
        user = User(username="alice", email="alice@example.com", password_hash="h")
        agent = Agent(name="agente")
        session.add_all([user, agent])
        await session.flush()
        thread = Thread(agent_id=agent.id, user_id=user.id)
        session.add(thread)
        await session.commit()
        return thread.id


async def test_postgres_queue_enqueue_claim_complete(
    isolated_sessionmaker: async_sessionmaker,
) -> None:
    thread_id = await _seed_thread(isolated_sessionmaker)
    queue = PostgresConsolidationQueue(isolated_sessionmaker)

    async with isolated_sessionmaker() as session:
        await queue.enqueue(session, thread_id=thread_id, agent_id=1, user_id=1)
        await session.commit()

    jobs = await queue.claim()
    assert len(jobs) == 1
    assert jobs[0].thread_id == thread_id
    assert jobs[0].attempts == 1

    await queue.complete(jobs[0].id)
    assert await queue.claim() == []


async def test_postgres_queue_enqueue_rolls_back_with_caller(
    isolated_sessionmaker: async_sessionmaker,
) -> None:
    """El encolado participa de la transaccion del turno (D14)."""
    thread_id = await _seed_thread(isolated_sessionmaker)
    queue = PostgresConsolidationQueue(isolated_sessionmaker)

    async with isolated_sessionmaker() as session:
        await queue.enqueue(session, thread_id=thread_id, agent_id=1, user_id=1)
        await session.rollback()

    assert await queue.claim() == []


async def test_postgres_queue_retries_after_failure_and_respects_max_attempts(
    isolated_sessionmaker: async_sessionmaker,
) -> None:
    thread_id = await _seed_thread(isolated_sessionmaker)
    queue = PostgresConsolidationQueue(isolated_sessionmaker, max_attempts=2)

    async with isolated_sessionmaker() as session:
        await queue.enqueue(session, thread_id=thread_id, agent_id=1, user_id=1)
        await session.commit()

    first = await queue.claim()
    assert len(first) == 1
    await queue.fail(first[0].id, "boom")

    second = await queue.claim()
    assert len(second) == 1
    assert second[0].attempts == 2
    await queue.fail(second[0].id, "boom")

    # Agotados los intentos, el trabajo queda fuera de la cola (dead-letter).
    assert await queue.claim() == []
