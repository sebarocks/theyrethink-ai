"""Spike S4 — replay del checkpointer por la API publica (gate de la Fase 5).

Script **desechable**: su entregable es la conclusion escrita en
`docs/spikes/S4-checkpointer-replay.md`.

Pregunta: ¿se puede reconstruir una conversacion historica en el checkpointer usando solo la
API publica del grafo (`CompiledStateGraph.aupdate_state`) y leerla despues por
`agent/service.py`, sin escribir filas a mano ni tocar el formato interno de la libreria?

Se ejecuta **sin red y sin base de datos**: `InMemorySaver` + `InMemoryStore`, y un LLM falso
que nunca se invoca (el replay no llama al modelo). La ruta que se prueba es exactamente
`AgentService.import_transcript`, la que usara el migrador de la Fase 5.

Uso:

    uv run python -m scripts.spike_s4
"""

from __future__ import annotations

import asyncio
import importlib.metadata as metadata

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from app.agent.consolidation import FakeConsolidationQueue
from app.agent.dto import AgentContext, MessageDTO
from app.agent.graph import build_chat_graph
from app.agent.service import AgentService

HISTORY = [
    MessageDTO(role="user", text="Hola, me llamo Ana."),
    MessageDTO(role="assistant", text="Hola Ana, ¿en qué te ayudo?"),
    MessageDTO(role="user", text="¿Te acuerdas de mi nombre?"),
    MessageDTO(role="assistant", text="Sí, Ana."),
]


class _NeverCalledLLM(BaseChatModel):
    """LLM que revienta si se invoca: el replay no debe llamar al modelo."""

    @property
    def _llm_type(self) -> str:
        return "spike-s4-never-called"

    def _generate(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: object,
    ) -> ChatResult:
        raise AssertionError("el replay no debe invocar al LLM")

    async def _agenerate(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: object | None = None,
        **kwargs: object,
    ) -> ChatResult:
        raise AssertionError("el replay no debe invocar al LLM")


async def _load_context(agent_id: int) -> AgentContext:
    return AgentContext(
        agent_id=agent_id, name="spike", profile="", identity_prompt="Eres un asistente."
    )


def _mark(ok: bool) -> str:
    return "OK  " if ok else "FALLA"


async def main() -> None:
    checkpointer = InMemorySaver()
    graph = build_chat_graph(
        llm=_NeverCalledLLM(),
        store=InMemoryStore(),
        load_context=_load_context,
        context_tokens=1_000,
        count_tokens=lambda _text: 1,
        checkpointer=checkpointer,
    )
    service = AgentService(
        chat_graph=graph,
        memory_graph=graph,  # no se usa en el replay
        store=InMemoryStore(),
        checkpointer=checkpointer,
        queue=FakeConsolidationQueue(),
        sessionmaker=None,  # type: ignore[arg-type]  # el replay no toca la base de dominio
        llm=_NeverCalledLLM(),
        count_tokens=lambda _text: 1,
    )

    print(f"langgraph = {metadata.version('langgraph')}")
    print(f"langgraph-checkpoint-postgres = {metadata.version('langgraph-checkpoint-postgres')}")
    print()

    # [A] Escribir el transcript por la API publica, sin SQL ni formato interno.
    try:
        await service.import_transcript(thread_id=1, messages=HISTORY)
        print(f"[A] aupdate_state (API publica) ..... {_mark(True)}")
    except Exception as error:  # noqa: BLE001 - el objetivo es clasificar el fallo
        print(
            f"[A] aupdate_state (API publica) ..... {_mark(False)} {type(error).__name__}: {error}"
        )
        return

    # [B] Leerlo por el servicio y comprobar fidelidad exacta.
    transcript = await service.read_messages(thread_id=1)
    got = [(message.role, message.text) for message in transcript]
    expected = [(message.role, message.text) for message in HISTORY]
    print(f"[B] read_messages round-trip fiel .. {_mark(got == expected)} ({len(got)} mensajes)")

    # [C] El replay no debe dejar `system_prompt` ni memoria en el estado persistido.
    snapshot = await graph.aget_state({"configurable": {"thread_id": "1"}})
    values = snapshot.values if snapshot else {}
    clean = "system_prompt" not in values
    print(f"[C] sin system_prompt persistido .... {_mark(clean)}")

    # [D] Un hilo distinto no ve el transcript importado.
    other = await service.read_messages(thread_id=999)
    print(f"[D] aislamiento por thread_id ...... {_mark(other == [])}")

    # [E] Reimportar el mismo transcript se rechaza: no puede duplicar la historia.
    duplicated = False
    try:
        await service.import_transcript(thread_id=1, messages=HISTORY)
        duplicated = True
    except ValueError:
        duplicated = False
    print(f"[E] reimportar se rechaza ........... {_mark(not duplicated)}")

    ok = got == expected and clean and other == [] and not duplicated
    print(f"\nResultado: {'CUMPLE' if ok else 'NO CUMPLE'}")


if __name__ == "__main__":
    asyncio.run(main())
