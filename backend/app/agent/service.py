"""API publica del nucleo del agente — la **costura unica** (AGENTS.md §3.2, ADR `0006`).

Los routers de FastAPI solo importan este modulo y solo ven DTOs de dominio: nunca
`BaseMessage` ni tipos de LangGraph/LangChain. Aqui viven `send_message()` (con stream),
`consolidate()`, `ensure_memory()` y el alta/baja de metadatos de hilo.

`threads` es **cache de UI, no fuente de verdad** (AGENTS.md §3.4): `message_count`,
`last_preview` y `title` los mantiene este servicio; si discrepan del checkpointer, manda el
checkpointer.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncIterator, Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START
from langgraph.store.base import BaseStore
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.consolidation import ConsolidationQueue
from app.agent.dto import ChatChunk, ConsolidationJobDTO, MessageDTO, ThreadMetadata
from app.agent.memory import MemoryFact, memory_namespace, read_facts, write_facts
from app.agent.observability import log_event
from app.models import Thread

__all__ = ["AgentService", "DEFAULT_THREAD_TITLE", "derive_title"]

DEFAULT_THREAD_TITLE = "Nueva conversación"
_PREVIEW_LENGTH = 200
_TITLE_LENGTH = 60


def derive_title(user_text: str) -> str:
    """Titulo de hilo a partir del primer mensaje del usuario."""
    text = " ".join(user_text.split())
    if not text:
        return DEFAULT_THREAD_TITLE
    return text[:_TITLE_LENGTH]


def _content_to_text(message: BaseMessage) -> str:
    """Normaliza el contenido de un mensaje (str o lista de bloques) a texto plano."""
    content = message.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "".join(parts)


def _conversation_text(messages: list[BaseMessage], since: int) -> str:
    """Transcripcion de los mensajes no consolidados (`since` = posicion ya cubierta).

    Se extraen **todos** los turnos pendientes, no solo el ultimo: si la cola se atrasa, un
    trabajo posterior no debe dejar atras los turnos anteriores (D7). El orden es el del
    checkpointer, que es la fuente de verdad.
    """
    lines: list[str] = []
    for message in messages[since:]:
        text = _content_to_text(message)
        if not text:
            continue
        if isinstance(message, HumanMessage):
            lines.append(f"Usuario: {text}")
        elif isinstance(message, AIMessage):
            lines.append(f"Agente: {text}")
    return "\n".join(lines)


class AgentService:
    """Nucleo del agente: chat, memoria y metadatos de hilo."""

    def __init__(
        self,
        *,
        chat_graph: Any,
        memory_graph: Any,
        store: BaseStore,
        checkpointer: BaseCheckpointSaver,
        queue: ConsolidationQueue,
        sessionmaker: async_sessionmaker[AsyncSession],
        llm: BaseChatModel,
        count_tokens: Callable[[str], int],
    ):
        self._chat_graph = chat_graph
        self._memory_graph = memory_graph
        self._store = store
        self._checkpointer = checkpointer
        self._queue = queue
        self._sessionmaker = sessionmaker
        self._llm = llm
        self._count_tokens = count_tokens

    # ------------------------------------------------------------------ chat

    async def send_message(
        self,
        *,
        agent_id: int,
        user_id: int,
        thread_id: int,
        text: str,
    ) -> AsyncIterator[ChatChunk]:
        """Envia un mensaje y devuelve la respuesta en streaming.

        El mensaje humano entra al estado del hilo (lo persiste el checkpointer); la memoria
        se inyecta de forma transitoria dentro del grafo y **no** queda en el estado (D7).
        """
        config = {"configurable": {"thread_id": str(thread_id)}}
        inputs = {
            "agent_id": agent_id,
            "user_id": user_id,
            "thread_id": str(thread_id),
            "messages": [HumanMessage(content=text)],
        }
        log_event("chat.send", thread_id=thread_id, agent_id=agent_id, user_id=user_id)
        async for chunk in self._chat_graph.astream(inputs, config=config, stream_mode="messages"):
            message_chunk, _metadata = chunk
            delta = _content_to_text(message_chunk)
            if delta:
                yield ChatChunk(text=delta)
        yield ChatChunk(done=True)

    async def read_messages(self, *, thread_id: int) -> list[MessageDTO]:
        """Transcript del hilo leido del **checkpointer** (D16).

        Solo se exponen los mensajes `user`/`assistant`: el `system_prompt` vive en su propio
        campo del estado y la memoria se inyecta de forma transitoria, asi que ninguno de los
        dos aparece aqui (D7).
        """
        snapshot = await self._chat_graph.aget_state(
            {"configurable": {"thread_id": str(thread_id)}}
        )
        messages = snapshot.values.get("messages", []) if snapshot else []
        transcript: list[MessageDTO] = []
        for message in messages:
            text = _content_to_text(message)
            if not text:
                continue
            if isinstance(message, HumanMessage):
                transcript.append(MessageDTO(role="user", text=text))
            elif isinstance(message, AIMessage):
                transcript.append(MessageDTO(role="assistant", text=text))
        return transcript

    async def import_transcript(self, *, thread_id: int, messages: list[MessageDTO]) -> None:
        """Reconstruye el transcript de un hilo historico en el checkpointer (S4, Fase 5).

        Usa `aupdate_state`, la API publica de LangGraph, y no escribe filas del checkpointer
        a mano (AGENTS.md §3.3). **Idempotente por rechazo**: si el hilo ya tiene transcript,
        falla en vez de duplicarlo, porque el reducer `add_messages` agregaria los mensajes.
        """
        if not messages:
            return
        if await self.read_messages(thread_id=thread_id):
            raise ValueError(f"el hilo {thread_id} ya tiene transcript importado")
        history: list[BaseMessage] = [
            HumanMessage(content=message.text)
            if message.role == "user"
            else AIMessage(content=message.text)
            for message in messages
        ]
        await self._chat_graph.aupdate_state(
            {"configurable": {"thread_id": str(thread_id)}},
            {"messages": history},
            as_node=START,
        )

    # -------------------------------------------------------------- memoria

    async def ensure_memory(
        self, *, agent_id: int, user_id: int, facts: list[MemoryFact]
    ) -> list[MemoryFact]:
        """Siembra hechos iniciales (agentes sembrados nacen con memoria, §5.3)."""
        return await write_facts(self._store, memory_namespace(agent_id, user_id), facts)

    async def read_memory(self, *, agent_id: int, user_id: int) -> list[MemoryFact]:
        """Hechos actuales del usuario para ese agente, en orden de insercion."""
        return await read_facts(self._store, memory_namespace(agent_id, user_id))

    async def consolidate(self, job: ConsolidationJobDTO) -> list[MemoryFact]:
        """Consolida los turnos pendientes de un trabajo de la cola (D7).

        Idempotente por dos marcadores de `threads`: la marca de agua temporal
        (`last_consolidated_at`, que descarta reintentos del mismo trabajo) y la posicion en
        el transcript (`last_consolidated_message_count`, que garantiza que ningun turno
        quede sin extraer aunque la cola acumule trabajos). La sesion no se mantiene abierta
        durante la llamada al LLM: se lee, se cierra, se extrae y se vuelve a abrir para los
        marcadores.
        """
        since = await self._consolidation_position(job)
        if since is None:
            log_event("memory.skip", thread_id=job.thread_id, reason="already_consolidated")
            return []

        messages = await self._thread_messages(job.thread_id)
        conversation = _conversation_text(messages, since)
        if not conversation:
            await self._mark_consolidated(job, position=len(messages))
            return []

        existing = await read_facts(self._store, memory_namespace(job.agent_id, job.user_id))
        result = await self._memory_graph.ainvoke(
            {
                "agent_id": job.agent_id,
                "user_id": job.user_id,
                "conversation": conversation,
                "existing_facts": [fact.content for fact in existing],
            }
        )
        await self._mark_consolidated(job, position=len(messages))
        return list(result.get("persisted", []))

    async def _consolidation_position(self, job: ConsolidationJobDTO) -> int | None:
        """Posicion ya consolidada, o `None` si el trabajo es un reintento ya cubierto."""
        async with self._sessionmaker() as session:
            thread = await session.get(Thread, job.thread_id)
            if thread is None:
                return None
            if (
                thread.last_consolidated_at is not None
                and thread.last_consolidated_at >= job.created_at
            ):
                return None
            return thread.last_consolidated_message_count

    async def _mark_consolidated(self, job: ConsolidationJobDTO, *, position: int) -> None:
        async with self._sessionmaker() as session:
            thread = await session.get(Thread, job.thread_id)
            if thread is None:
                return
            thread.last_consolidated_at = job.created_at
            thread.last_consolidated_message_count = max(
                thread.last_consolidated_message_count, position
            )
            await session.commit()

    async def _thread_messages(self, thread_id: int) -> list[BaseMessage]:
        snapshot = await self._chat_graph.aget_state(
            {"configurable": {"thread_id": str(thread_id)}}
        )
        return list(snapshot.values.get("messages", [])) if snapshot else []

    # ------------------------------------------------------------- hilos

    async def create_thread(
        self,
        session: AsyncSession,
        *,
        agent_id: int,
        user_id: int,
        title: str = DEFAULT_THREAD_TITLE,
    ) -> ThreadMetadata:
        """Alta de metadatos de hilo. No hace commit: participa de la transaccion del llamador."""
        thread = Thread(agent_id=agent_id, user_id=user_id, title=title)
        session.add(thread)
        await session.flush()
        return _to_metadata(thread)

    async def get_thread(self, session: AsyncSession, thread_id: int) -> ThreadMetadata | None:
        thread = await session.get(Thread, thread_id)
        return _to_metadata(thread) if thread is not None else None

    async def list_threads(self, session: AsyncSession, *, user_id: int) -> list[ThreadMetadata]:
        rows = (
            await session.execute(
                select(Thread)
                .where(Thread.user_id == user_id)
                .order_by(Thread.updated_at.desc(), Thread.id.desc())
            )
        ).scalars()
        return [_to_metadata(thread) for thread in rows]

    async def record_turn(
        self,
        session: AsyncSession,
        *,
        thread_id: int,
        user_text: str,
        assistant_text: str,
    ) -> None:
        """Actualiza la cache de UI y **encola la consolidacion en la misma transaccion**.

        No hace commit: el llamador cierra la transaccion, de modo que metadatos y trabajo se
        confirman juntos (D14) o no se confirman.
        """
        thread = await session.get(Thread, thread_id)
        if thread is None:
            raise LookupError(f"hilo {thread_id} inexistente")
        thread.message_count += 2
        thread.last_preview = assistant_text.strip()[:_PREVIEW_LENGTH]
        if thread.title == DEFAULT_THREAD_TITLE:
            thread.title = derive_title(user_text)
        thread.updated_at = dt.datetime.now(dt.UTC)
        await self._queue.enqueue(
            session, thread_id=thread.id, agent_id=thread.agent_id, user_id=thread.user_id
        )

    async def delete_thread(self, session: AsyncSession, *, thread_id: int) -> None:
        """Baja de hilo (D10): borra checkpoint y fila `threads`; **no** toca el `Store`."""
        thread = await session.get(Thread, thread_id)
        if thread is None:
            return
        await self._checkpointer.adelete_thread(str(thread_id))
        await session.delete(thread)


def _to_metadata(thread: Thread) -> ThreadMetadata:
    return ThreadMetadata(
        id=thread.id,
        agent_id=thread.agent_id,
        user_id=thread.user_id,
        title=thread.title,
        message_count=thread.message_count,
        last_preview=thread.last_preview,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        last_consolidated_at=thread.last_consolidated_at,
    )
