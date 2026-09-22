"""Definicion de los grafos LangGraph: chat y memoria separados (propuesta §5.2).

Dos grafos comparten el mismo `Store`; el de chat usa checkpointer y el de memoria **no**
(no es una conversacion). Separarlos permite que la consolidacion corra fuera del camino de
respuesta del usuario (cola externa, D7).

Invariante critica (D7): la memoria se inyecta **al final y de forma transitoria**. El nodo
`respond` la lee del `Store` y la coloca entre el historial y el mensaje nuevo **sin
escribirla en el estado**, de modo que el checkpointer no la persiste y el prefijo
`[system][historial]` queda byte-estable.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import Runnable
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.store.base import BaseStore

from app.agent.dto import AgentContext
from app.agent.memory import (
    ExtractedMemories,
    MemoryFact,
    injection_budget_tokens,
    memory_namespace,
    read_facts,
    select_injectable_facts,
    write_facts,
)
from app.agent.observability import log_event
from app.agent.prompts import (
    build_memory_block,
    build_memory_extraction_prompt,
    build_system_prompt,
)

__all__ = ["ChatState", "MemoryState", "build_chat_graph", "build_memory_graph"]

# Cargador de contexto inyectable: en produccion lee la base; en tests es un doble.
ContextLoader = Callable[[int], Awaitable[AgentContext]]
TokenCounter = Callable[[str], int]


class ChatState(TypedDict, total=False):
    """Estado del grafo de chat.

    `system_prompt` se persiste (es el prefijo estable y cacheable). La memoria **no** tiene
    campo aqui a proposito: si lo tuviera, el checkpointer la guardaria y se repetiria en cada
    turno (D7).
    """

    agent_id: int
    user_id: int
    thread_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    system_prompt: str


class MemoryState(TypedDict, total=False):
    """Estado del grafo de memoria (sin checkpointer)."""

    agent_id: int
    user_id: int
    conversation: str
    existing_facts: list[str]
    extracted: list[MemoryFact]
    persisted: list[MemoryFact]


def _coerce_facts(result: Any) -> list[MemoryFact]:
    """Normaliza la salida del extractor a `list[MemoryFact]` (acepta modelo o dict)."""
    if isinstance(result, ExtractedMemories):
        return list(result.facts)
    if isinstance(result, dict):
        return ExtractedMemories.model_validate(result).facts
    raise TypeError(f"salida del extractor no soportada: {type(result)!r}")


def build_chat_graph(
    *,
    llm: BaseChatModel,
    store: BaseStore,
    load_context: ContextLoader,
    context_tokens: int,
    count_tokens: TokenCounter,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Compila el grafo de chat: `load_context` -> `respond`."""

    async def load_context_node(state: ChatState) -> dict[str, str]:
        context = await load_context(state["agent_id"])
        system_prompt = build_system_prompt(
            identity_prompt=context.identity_prompt,
            profile=context.profile,
            sources=context.sources,
        )
        return {"system_prompt": system_prompt}

    async def respond(state: ChatState) -> dict[str, list[BaseMessage]]:
        namespace = memory_namespace(state["agent_id"], state["user_id"])
        facts = await read_facts(store, namespace)
        injectable = select_injectable_facts(
            facts,
            budget_tokens=injection_budget_tokens(context_tokens),
            count_tokens=count_tokens,
        )
        memory_block = build_memory_block([fact.content for fact in injectable])

        messages = list(state["messages"])
        # Orden canonico: [system][historial][memoria][mensaje nuevo] (D7).
        prompt: list[BaseMessage] = [SystemMessage(content=state["system_prompt"]), *messages[:-1]]
        if memory_block:
            prompt.append(SystemMessage(content=memory_block))
        prompt.append(messages[-1])

        log_event(
            "chat.respond",
            thread_id=state.get("thread_id"),
            agent_id=state.get("agent_id"),
            user_id=state.get("user_id"),
            injected_facts=len(injectable),
        )
        response = await llm.ainvoke(prompt)
        return {"messages": [response]}

    graph = StateGraph(ChatState)
    graph.add_node("load_context", load_context_node)
    graph.add_node("respond", respond)
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer, store=store)


def build_memory_graph(*, extractor: Runnable[Any, Any], store: BaseStore):
    """Compila el grafo de memoria: `extract` -> `persist`. **Sin checkpointer** (D7)."""

    async def extract(state: MemoryState) -> dict[str, list[MemoryFact]]:
        prompt = build_memory_extraction_prompt(
            conversation=state["conversation"],
            existing_facts=state.get("existing_facts", []),
        )
        result = await extractor.ainvoke(prompt)
        return {"extracted": _coerce_facts(result)}

    async def persist(state: MemoryState) -> dict[str, list[MemoryFact]]:
        namespace = memory_namespace(state["agent_id"], state["user_id"])
        written = await write_facts(store, namespace, state.get("extracted", []))
        log_event(
            "memory.persist",
            agent_id=state.get("agent_id"),
            user_id=state.get("user_id"),
            written=len(written),
        )
        return {"persisted": written}

    graph = StateGraph(MemoryState)
    graph.add_node("extract", extract)
    graph.add_node("persist", persist)
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "persist")
    graph.add_edge("persist", END)
    return graph.compile(store=store)
