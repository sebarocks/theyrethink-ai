"""Test de humo del montaje del nucleo (`agent_runtime`).

Verifica el cableado (nombres de parametros, compilacion de grafos, orden de `setup()`) sin
red ni llamadas al LLM: la fabrica y el extractor se sustituyen por dobles.
"""

import pytest

from app.agent import runtime as runtime_module
from app.agent.service import AgentService
from app.config import Settings
from tests.fakes import RecordingFakeLLM, fake_extractor

DATABASE_URL = "postgresql+asyncpg://theyrethink:theyrethink@localhost:5432/theyrethink"


async def test_agent_runtime_wires_the_service(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        _env_file=None,
        secret_key="x" * 32,
        database_url=DATABASE_URL,
        consolidation_worker_enabled=False,
    )
    monkeypatch.setattr(runtime_module, "get_settings", lambda: settings)
    monkeypatch.setattr(runtime_module, "get_chat_llm", lambda: RecordingFakeLLM())
    monkeypatch.setattr(runtime_module, "get_extractor", lambda: fake_extractor())

    async def fake_resolve_context_tokens(_model: object) -> int:
        return 1_000

    monkeypatch.setattr(runtime_module, "resolve_context_tokens", fake_resolve_context_tokens)

    async with runtime_module.agent_runtime() as service:
        assert isinstance(service, AgentService)
