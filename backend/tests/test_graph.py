"""Tests de los grafos: inyeccion transitoria de memoria y prefijo byte-estable (D7)."""

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from app.agent.dto import AgentContext
from app.agent.graph import build_chat_graph, build_memory_graph
from app.agent.memory import MemoryFact, memory_namespace, write_facts
from tests.fakes import RecordingFakeLLM, fake_extractor

CONTEXT = AgentContext(
    agent_id=1,
    name="agente",
    profile="NOMBRE:\nAna",
    identity_prompt="Eres un profesor.",
    sources=(),
)


async def _load_context(agent_id: int) -> AgentContext:
    return CONTEXT


def _chat_graph(store: InMemoryStore, llm: RecordingFakeLLM, checkpointer: InMemorySaver):
    return build_chat_graph(
        llm=llm,
        store=store,
        load_context=_load_context,
        context_tokens=1_000,
        count_tokens=lambda _text: 1,
        checkpointer=checkpointer,
    )


async def test_chat_graph_injects_memory_before_new_message() -> None:
    store = InMemoryStore()
    llm = RecordingFakeLLM(response="hola")
    graph = _chat_graph(store, llm, InMemorySaver())
    await write_facts(store, memory_namespace(1, 1), [MemoryFact(content="vive en Santiago")])

    await graph.ainvoke(
        {
            "agent_id": 1,
            "user_id": 1,
            "thread_id": "1",
            "messages": [HumanMessage(content="hola")],
        },
        config={"configurable": {"thread_id": "1"}},
    )

    sent = llm.calls[-1]
    assert sent[0].content.startswith("Eres un profesor.")  # [system]
    assert sent[-1].content == "hola"  # [mensaje nuevo]
    assert sent[-2].content == "MEMORIA DEL USUARIO:\n- vive en Santiago"  # [memoria]


async def test_chat_graph_does_not_persist_injected_memory() -> None:
    store = InMemoryStore()
    llm = RecordingFakeLLM(response="hola")
    checkpointer = InMemorySaver()
    graph = _chat_graph(store, llm, checkpointer)
    await write_facts(store, memory_namespace(1, 1), [MemoryFact(content="vive en Santiago")])
    config = {"configurable": {"thread_id": "1"}}

    await graph.ainvoke(
        {
            "agent_id": 1,
            "user_id": 1,
            "thread_id": "1",
            "messages": [HumanMessage(content="hola")],
        },
        config=config,
    )

    state = await graph.aget_state(config)
    assert "memories" not in state.values
    assert "memory_block" not in state.values
    # Solo el mensaje humano y la respuesta: la memoria no quedo en el estado.
    assert [type(message).__name__ for message in state.values["messages"]] == [
        "HumanMessage",
        "AIMessage",
    ]


async def test_chat_graph_system_prompt_is_byte_stable_between_turns() -> None:
    store = InMemoryStore()
    llm = RecordingFakeLLM(response="ok")
    graph = _chat_graph(store, llm, InMemorySaver())
    config = {"configurable": {"thread_id": "1"}}

    for text in ("primero", "segundo", "tercero"):
        await graph.ainvoke(
            {
                "agent_id": 1,
                "user_id": 1,
                "thread_id": "1",
                "messages": [HumanMessage(content=text)],
            },
            config=config,
        )

    system_prompts = {call[0].content for call in llm.calls}
    assert len(system_prompts) == 1  # identico en los tres turnos

    # El historial de un turno es prefijo del siguiente (sin la memoria ni el mensaje nuevo).
    second_history = llm.calls[1][1:-2]
    third_history = llm.calls[2][1 : 1 + len(second_history)]
    assert [message.content for message in third_history] == [
        message.content for message in second_history
    ]


async def test_memory_graph_extracts_and_persists_with_dedup() -> None:
    store = InMemoryStore()
    graph = build_memory_graph(
        extractor=fake_extractor([MemoryFact(content="vive en Santiago")]), store=store
    )

    first = await graph.ainvoke(
        {"agent_id": 1, "user_id": 1, "conversation": "Usuario: hola", "existing_facts": []}
    )
    assert [fact.content for fact in first["persisted"]] == ["vive en Santiago"]

    second = await graph.ainvoke(
        {
            "agent_id": 1,
            "user_id": 1,
            "conversation": "Usuario: hola",
            "existing_facts": ["vive en Santiago"],
        }
    )
    assert second["persisted"] == []
