"""Tests de la fabrica LLM: configuracion, contexto en runtime y taxonomia de errores."""

from types import SimpleNamespace

import pytest

from app.agent import llm as llm_module
from app.agent.llm import (
    LLMConfigurationError,
    LLMProviderError,
    _extract_context_tokens,
    _model_id_candidates,
    count_tokens,
    get_chat_llm,
    resolve_context_tokens,
)
from app.config import Settings
from tests.fakes import RecordingFakeLLM

DATABASE_URL = "postgresql+asyncpg://theyrethink:theyrethink@localhost:5432/theyrethink"


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"secret_key": "x" * 32, "database_url": DATABASE_URL}
    values.update(overrides)
    return Settings(_env_file=None, **values)


class _ModelWithProfile:
    profile = {"max_input_tokens": 1_050_000}


class _ModelWithoutProfile:
    profile = None


# --------------------------------------------------------------- extraccion pura


def test_extract_context_tokens_probes_known_fields() -> None:
    assert _extract_context_tokens({"context_length": 1_050_000}) == 1_050_000
    assert _extract_context_tokens({"context_window": 128_000}) == 128_000
    assert _extract_context_tokens({"max_input_tokens": 200_000}) == 200_000
    assert _extract_context_tokens({"max_context_length": 32_768}) == 32_768


def test_extract_context_tokens_reads_openrouter_top_provider() -> None:
    payload = {"id": "openai/gpt-5.6-luna", "top_provider": {"context_length": 1_050_000}}
    assert _extract_context_tokens(payload) == 1_050_000


def test_extract_context_tokens_returns_none_when_absent_or_invalid() -> None:
    assert _extract_context_tokens({"id": "x"}) is None
    assert _extract_context_tokens({"context_length": 0}) is None
    assert _extract_context_tokens({"context_length": "muchos"}) is None


def test_model_id_candidates_accepts_langchain_prefix() -> None:
    assert _model_id_candidates("openai/gpt-5.6-luna") == {"openai/gpt-5.6-luna"}
    assert _model_id_candidates("openai:gpt-4.1") == {"openai:gpt-4.1", "gpt-4.1"}


# --------------------------------------------------------------- descubrimiento


class _FakeModels:
    def __init__(self, entries: list[SimpleNamespace]) -> None:
        self._entries = entries

    def list(self):
        async def _iterate():
            for entry in self._entries:
                yield entry

        return _iterate()


class _FakeClient:
    def __init__(self, entries: list[SimpleNamespace]) -> None:
        self.models = _FakeModels(entries)

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False


async def test_discovery_reads_context_from_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = SimpleNamespace(
        id="openai/gpt-5.6-luna",
        model_dump=lambda: {"id": "openai/gpt-5.6-luna", "context_length": 1_050_000},
    )
    monkeypatch.setattr(llm_module, "AsyncOpenAI", lambda **_kwargs: _FakeClient([entry]))

    settings = _settings(
        llm_base_url="https://openrouter.ai/api/v1",
        llm_api_key="secret",
        llm_model="openai/gpt-5.6-luna",
    )
    assert await llm_module._discover_context_tokens(settings) == 1_050_000


async def test_discovery_returns_none_when_model_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = SimpleNamespace(id="otro/modelo", model_dump=lambda: {"context_length": 1})
    monkeypatch.setattr(llm_module, "AsyncOpenAI", lambda **_kwargs: _FakeClient([entry]))

    settings = _settings(
        llm_base_url="https://openrouter.ai/api/v1",
        llm_api_key="secret",
        llm_model="openai/gpt-5.6-luna",
    )
    assert await llm_module._discover_context_tokens(settings) is None


# --------------------------------------------------------------- resolucion


async def test_resolve_context_tokens_uses_provider_first(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_discover(_settings: Settings) -> int:
        return 1_050_000

    monkeypatch.setattr(llm_module, "_discover_context_tokens", fake_discover)
    # Aunque el perfil diga otra cosa, manda el proveedor.
    assert await resolve_context_tokens(_ModelWithProfile(), _settings()) == 1_050_000


async def test_resolve_context_tokens_falls_back_to_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_discover(_settings: Settings) -> None:
        return None

    monkeypatch.setattr(llm_module, "_discover_context_tokens", fake_discover)
    assert await resolve_context_tokens(_ModelWithProfile(), _settings()) == 1_050_000


async def test_resolve_context_tokens_falls_back_to_config(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_discover(_settings: Settings) -> None:
        return None

    monkeypatch.setattr(llm_module, "_discover_context_tokens", fake_discover)
    settings = _settings(llm_context_tokens=128_000)
    assert await resolve_context_tokens(_ModelWithoutProfile(), settings) == 128_000


async def test_resolve_context_tokens_fails_without_any_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_discover(_settings: Settings) -> None:
        return None

    monkeypatch.setattr(llm_module, "_discover_context_tokens", fake_discover)
    with pytest.raises(LLMConfigurationError):
        await resolve_context_tokens(_ModelWithoutProfile(), _settings())


# --------------------------------------------------------------- fabrica


def test_get_chat_llm_requires_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    get_chat_llm.cache_clear()
    monkeypatch.setattr(llm_module, "get_settings", lambda: _settings())
    try:
        with pytest.raises(LLMConfigurationError):
            get_chat_llm()
    finally:
        get_chat_llm.cache_clear()


def test_count_tokens_wraps_unsupported_tokenizer() -> None:
    """Un modelo sin tokenizador debe fallar con error tipado, no con un error de libreria."""
    with pytest.raises(LLMProviderError):
        count_tokens(RecordingFakeLLM(), "hola")
