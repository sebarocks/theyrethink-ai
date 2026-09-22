"""Tests del servicio: streaming, metadatos de hilo, cola y consolidacion.

El servicio toca la base (metadatos y cola), asi que estos tests usan un esquema efimero
aislado por test; los grafos siguen con dobles en memoria (AGENTS.md §6).
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agent.consolidation import FakeConsolidationQueue
from app.agent.dto import AgentContext
from app.agent.graph import build_chat_graph, build_memory_graph
from app.agent.memory import MemoryFact
from app.agent.service import DEFAULT_THREAD_TITLE, AgentService
from app.models import Agent, Thread, User
from tests.fakes import RecordingFakeLLM, fake_extractor

CONTEXT = AgentContext(
    agent_id=1, name="agente", profile="", identity_prompt="Eres un asistente.", sources=()
)


async def _load_context(agent_id: int) -> AgentContext:
    return CONTEXT


def _service(
    sessionmaker: async_sessionmaker,
    *,
    llm: RecordingFakeLLM | None = None,
    extractor: object | None = None,
    store: InMemoryStore | None = None,
    checkpointer: InMemorySaver | None = None,
    queue: FakeConsolidationQueue | None = None,
) -> AgentService:
    store = store or InMemoryStore()
    checkpointer = checkpointer or InMemorySaver()
    llm = llm or RecordingFakeLLM(response="respuesta del agente")
    extractor = extractor or fake_extractor()
    queue = queue or FakeConsolidationQueue()
    chat_graph = build_chat_graph(
        llm=llm,
        store=store,
        load_context=_load_context,
        context_tokens=1_000,
        count_tokens=lambda _text: 1,
        checkpointer=checkpointer,
    )
    memory_graph = build_memory_graph(extractor=extractor, store=store)
    return AgentService(
        chat_graph=chat_graph,
        memory_graph=memory_graph,
        store=store,
        checkpointer=checkpointer,
        queue=queue,
        sessionmaker=sessionmaker,
        llm=llm,
        count_tokens=lambda _text: 1,
    )


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


async def test_send_message_streams_and_persists_turn(sessionmaker: async_sessionmaker) -> None:
    thread_id = await _seed_thread(sessionmaker)
    service = _service(sessionmaker)

    chunks = [
        chunk
        async for chunk in service.send_message(
            agent_id=1, user_id=1, thread_id=thread_id, text="hola"
        )
    ]

    assert "".join(chunk.text for chunk in chunks) == "respuesta del agente"
    assert chunks[-1].done is True

    snapshot = await service._chat_graph.aget_state({"configurable": {"thread_id": str(thread_id)}})
    assert [type(message).__name__ for message in snapshot.values["messages"]] == [
        "HumanMessage",
        "AIMessage",
    ]


async def test_record_turn_updates_metadata_and_enqueues_atomically(
    sessionmaker: async_sessionmaker,
) -> None:
    thread_id = await _seed_thread(sessionmaker)
    queue = FakeConsolidationQueue()
    service = _service(sessionmaker, queue=queue)

    async with sessionmaker() as session:
        await service.record_turn(
            session, thread_id=thread_id, user_text="¿Quién eres?", assistant_text="Soy un agente."
        )
        await session.commit()

    async with sessionmaker() as session:
        thread = await session.get(Thread, thread_id)
        assert thread.message_count == 2
        assert thread.last_preview == "Soy un agente."
        assert thread.title == "¿Quién eres?"
    assert len(queue.jobs) == 1


async def test_record_turn_rolls_back_metadata_and_job_together(
    sessionmaker: async_sessionmaker,
) -> None:
    """D14: metadatos y trabajo se confirman juntos o no se confirman."""
    thread_id = await _seed_thread(sessionmaker)
    queue = FakeConsolidationQueue()
    service = _service(sessionmaker, queue=queue)

    async with sessionmaker() as session:
        await service.record_turn(
            session, thread_id=thread_id, user_text="hola", assistant_text="hola"
        )
        await session.rollback()

    async with sessionmaker() as session:
        thread = await session.get(Thread, thread_id)
        assert thread.message_count == 0
        assert thread.title == DEFAULT_THREAD_TITLE


async def test_consolidate_is_idempotent_by_watermark(sessionmaker: async_sessionmaker) -> None:
    thread_id = await _seed_thread(sessionmaker)
    store = InMemoryStore()
    queue = FakeConsolidationQueue()
    service = _service(
        sessionmaker,
        store=store,
        queue=queue,
        extractor=fake_extractor([MemoryFact(content="vive en Santiago")]),
    )

    async for _ in service.send_message(agent_id=1, user_id=1, thread_id=thread_id, text="hola"):
        pass
    async with sessionmaker() as session:
        await service.record_turn(
            session, thread_id=thread_id, user_text="hola", assistant_text="respuesta del agente"
        )
        await session.commit()

    job = (await queue.claim())[0]
    persisted = await service.consolidate(job)
    assert [fact.content for fact in persisted] == ["vive en Santiago"]

    # Reintento del mismo trabajo: la marca de agua lo descarta.
    assert await service.consolidate(job) == []
    assert len(await service.read_memory(agent_id=1, user_id=1)) == 1


async def test_delete_thread_removes_checkpoint_and_row_but_not_memory(
    sessionmaker: async_sessionmaker,
) -> None:
    thread_id = await _seed_thread(sessionmaker)
    store = InMemoryStore()
    service = _service(sessionmaker, store=store)

    async for _ in service.send_message(agent_id=1, user_id=1, thread_id=thread_id, text="hola"):
        pass
    await service.ensure_memory(
        agent_id=1, user_id=1, facts=[MemoryFact(content="vive en Santiago")]
    )

    async with sessionmaker() as session:
        await service.delete_thread(session, thread_id=thread_id)
        await session.commit()

    async with sessionmaker() as session:
        assert await session.get(Thread, thread_id) is None
    snapshot = await service._chat_graph.aget_state({"configurable": {"thread_id": str(thread_id)}})
    assert snapshot.values == {}
    assert len(await service.read_memory(agent_id=1, user_id=1)) == 1
