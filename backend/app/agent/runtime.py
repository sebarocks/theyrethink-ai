"""Montaje del nucleo del agente para el `lifespan` de FastAPI.

Aqui se crean el checkpointer y el `Store` de LangGraph (`setup()` idempotente, spike S2), se
compilan los grafos **una sola vez** y se arranca el worker de consolidacion. El resto del
backend solo ve el `AgentService` que devuelve este contexto.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from sqlalchemy.engine import make_url

from app.agent.consolidation import ConsolidationWorker, PostgresConsolidationQueue
from app.agent.context import load_agent_context
from app.agent.dto import AgentContext
from app.agent.graph import build_chat_graph, build_memory_graph
from app.agent.llm import count_tokens, get_chat_llm, get_extractor, resolve_context_tokens
from app.agent.service import AgentService
from app.config import get_settings
from app.db import get_sessionmaker

__all__ = ["agent_runtime"]


def _libpq_dsn(database_url: object) -> str:
    """DSN libpq para el checkpointer y el `Store` de LangGraph.

    LangGraph usa `psycopg`, que no entiende el esquema `postgresql+asyncpg://` de SQLAlchemy:
    hay que quitarle el driver.
    """
    return (
        make_url(str(database_url))
        .set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )


@asynccontextmanager
async def agent_runtime() -> AsyncIterator[AgentService]:
    """Construye el servicio del agente y lo apaga de forma ordenada."""
    settings = get_settings()
    sessionmaker = get_sessionmaker()
    dsn = _libpq_dsn(settings.database_url)

    async with AsyncPostgresSaver.from_conn_string(dsn) as checkpointer:
        await checkpointer.setup()
        async with AsyncPostgresStore.from_conn_string(dsn) as store:
            await store.setup()

            llm = get_chat_llm()
            extractor = get_extractor()
            context_tokens = await resolve_context_tokens(llm)

            async def _load_context(agent_id: int) -> AgentContext:
                async with sessionmaker() as session:
                    return await load_agent_context(session, agent_id)

            chat_graph = build_chat_graph(
                llm=llm,
                store=store,
                load_context=_load_context,
                context_tokens=context_tokens,
                count_tokens=partial(count_tokens, llm),
                checkpointer=checkpointer,
            )
            memory_graph = build_memory_graph(extractor=extractor, store=store)

            queue = PostgresConsolidationQueue(
                sessionmaker, max_attempts=settings.consolidation_max_attempts
            )
            service = AgentService(
                chat_graph=chat_graph,
                memory_graph=memory_graph,
                store=store,
                checkpointer=checkpointer,
                queue=queue,
                sessionmaker=sessionmaker,
                llm=llm,
                count_tokens=partial(count_tokens, llm),
            )

            worker = ConsolidationWorker(
                queue=queue,
                consolidate=service.consolidate,
                interval_seconds=settings.consolidation_interval_seconds,
            )
            if settings.consolidation_worker_enabled:
                worker.start()
            try:
                yield service
            finally:
                await worker.stop()
