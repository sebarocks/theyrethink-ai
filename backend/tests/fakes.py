"""Dobles de test del nucleo del agente (AGENTS.md §6).

El nucleo se testea **sin I/O real**: `FakeLLM`, `InMemorySaver`, `InMemoryStore` y cola
falsa. Si un test del nucleo necesitara red o base de datos, el codigo estaria mal
estructurado.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import Field

from app.agent.memory import ExtractedMemories, MemoryFact

__all__ = ["RecordingFakeLLM", "fake_extractor"]


class RecordingFakeLLM(BaseChatModel):
    """LLM falso que registra los mensajes que recibe y emite tokens por callback.

    Emitir `on_llm_new_token` permite ejercitar `stream_mode="messages"` sin red.
    """

    response: str = "respuesta del agente"
    calls: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "recording-fake"

    def _tokens(self) -> list[str]:
        return [f"{token} " for token in self.response.split(" ")]

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: object,
    ) -> ChatResult:
        self.calls.append(list(messages))
        for token in self._tokens():
            if run_manager is not None:
                run_manager.on_llm_new_token(token)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.response))])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: object,
    ) -> ChatResult:
        self.calls.append(list(messages))
        for token in self._tokens():
            if run_manager is not None:
                await run_manager.on_llm_new_token(token)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.response))])


def fake_extractor(
    facts: Sequence[MemoryFact] = (),
    *,
    calls: list[str] | None = None,
) -> Callable[[str], ExtractedMemories]:
    """Extractor falso: devuelve hechos fijos y, opcionalmente, registra los prompts."""

    async def _run(prompt: str) -> ExtractedMemories:
        if calls is not None:
            calls.append(prompt)
        return ExtractedMemories(facts=list(facts))

    return RunnableLambda(_run)
