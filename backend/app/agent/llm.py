"""Fabrica del cliente LLM — **unica puerta a la libreria** (D15, ADR `0004`).

Proveedor y modelo llegan por variables de entorno sobre una API OpenAI-compatible; el
codigo no fija ninguno. El chat va en streaming y el extractor de memoria va aparte, con
`temperature=0`, sin streaming y con salida estructurada (spike S1).

Los errores del proveedor se tipan y se propagan con mensaje claro: si un modelo no cumple
una condicion, el fallo debe ser explicito, no silencioso (S1, consecuencias para Fase 2).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from functools import lru_cache
from typing import Any, cast

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from openai import AsyncOpenAI

from app.agent.memory import ExtractedMemories
from app.agent.observability import log_event
from app.config import Settings, get_settings

__all__ = [
    "LLMConfigurationError",
    "LLMError",
    "LLMProviderError",
    "count_tokens",
    "get_chat_llm",
    "get_extractor",
    "resolve_context_tokens",
]

# Campos con los que los proveedores OpenAI-compatibles publican el contexto del modelo en
# `GET /models`. OpenRouter usa `context_length` (a veces anidado en `top_provider`); otros
# usan `context_window` o `max_input_tokens`.
_CONTEXT_FIELDS = ("context_length", "context_window", "max_input_tokens", "max_context_length")


class LLMError(RuntimeError):
    """Base de la taxonomia de errores del cliente LLM."""


class LLMConfigurationError(LLMError):
    """Falta configuracion del proveedor (D15) o no se puede derivar el contexto del modelo."""


class LLMProviderError(LLMError):
    """El proveedor fallo al atender la peticion."""


def _require_settings(settings: Settings) -> None:
    missing = [
        name
        for name, value in (
            ("LLM_BASE_URL", settings.llm_base_url),
            ("LLM_API_KEY", settings.llm_api_key),
            ("LLM_MODEL", settings.llm_model),
        )
        if not value
    ]
    if missing:
        raise LLMConfigurationError(
            "configuracion LLM incompleta (D15): faltan " + ", ".join(missing)
        )


@lru_cache
def get_chat_llm(*, temperature: float = 0.7, streaming: bool = True) -> BaseChatModel:
    """Cliente de chat OpenAI-compatible, cacheado por temperatura y modo streaming.

    `streaming=True` para el chat; el extractor de memoria lo pide con `streaming=False`
    porque la salida estructurada necesita la respuesta completa (S1).
    """
    settings = get_settings()
    _require_settings(settings)
    return cast(
        BaseChatModel,
        init_chat_model(
            settings.llm_model,
            model_provider="openai",
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            temperature=temperature,
            streaming=streaming,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        ),
    )


@lru_cache
def get_extractor() -> Runnable[Any, Any]:
    """Extractor de memoria con salida estructurada (D7).

    Metodo preferido `json_schema` (impone el esquema); `function_calling` es el *fallback*
    equivalente. `json_mode` no basta porque solo garantiza JSON valido (S1).
    """
    settings = get_settings()
    model = get_chat_llm(temperature=0.0, streaming=False)
    return model.with_structured_output(
        ExtractedMemories,
        method=settings.llm_structured_output_method,
    )


def _model_id_candidates(model: str) -> set[str]:
    """Ids con los que buscar el modelo en `GET /models`.

    Acepta tanto el id del proveedor (`openai/gpt-5.6-luna`) como el formato de LangChain
    (`openai:gpt-4.1`), del que se descarta el prefijo de proveedor.
    """
    return {model, model.split(":", 1)[-1]}


def _extract_context_tokens(payload: Mapping[str, Any]) -> int | None:
    """Extrae el contexto de la entrada de `GET /models`, probando los campos conocidos."""
    for field in _CONTEXT_FIELDS:
        value = payload.get(field)
        if isinstance(value, int) and value > 0:
            return value
    top_provider = payload.get("top_provider")
    if isinstance(top_provider, Mapping):
        value = top_provider.get("context_length")
        if isinstance(value, int) and value > 0:
            return value
    return None


async def _discover_context_tokens(settings: Settings) -> int | None:
    """Pregunta al proveedor el contexto del modelo via `GET /models` (OpenAI-compatible).

    Es la fuente autoritativa y la primera que se consulta. Si el endpoint no responde o no
    publica el contexto, devuelve `None` y se cae a las fuentes siguientes.
    """
    if not (settings.llm_base_url and settings.llm_api_key and settings.llm_model):
        return None
    candidates = _model_id_candidates(settings.llm_model)
    try:
        client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_seconds,
        )
        async with client:
            async for entry in client.models.list():
                if entry.id in candidates:
                    return _extract_context_tokens(entry.model_dump())
    except Exception as error:  # noqa: BLE001 - el descubrimiento es best-effort
        log_event(
            "llm.context_discovery_failed",
            level=logging.WARNING,
            error=str(error),
        )
        return None
    return None


def _profile_context_tokens(model: BaseChatModel) -> int | None:
    """Contexto desde el perfil del modelo de LangChain (dataset estatico de models.dev)."""
    profile = getattr(model, "profile", None)
    if isinstance(profile, dict):
        value = profile.get("max_input_tokens")
        if isinstance(value, int) and value > 0:
            return value
    return None


async def resolve_context_tokens(model: BaseChatModel, settings: Settings | None = None) -> int:
    """Deriva el contexto del modelo **en runtime**, sin hardcodear un numero (D7, §4 hueco 11).

    Orden de fuentes: **(1)** el proveedor via `GET /models` —la autoridad—; **(2)** el perfil
    del modelo de LangChain; **(3)** `LLM_CONTEXT_TOKENS` como *override* explicito para
    proveedores que no publican contexto (p. ej. la API de OpenAI). Si ninguna responde, falla
    con un error claro en vez de inventarse un techo.
    """
    settings = settings or get_settings()

    discovered = await _discover_context_tokens(settings)
    if discovered is not None:
        log_event("llm.context_resolved", source="provider", context_tokens=discovered)
        return discovered

    profile_tokens = _profile_context_tokens(model)
    if profile_tokens is not None:
        log_event("llm.context_resolved", source="model_profile", context_tokens=profile_tokens)
        return profile_tokens

    if settings.llm_context_tokens:
        log_event(
            "llm.context_resolved", source="config", context_tokens=settings.llm_context_tokens
        )
        return settings.llm_context_tokens

    raise LLMConfigurationError(
        "no se pudo derivar el contexto del modelo: el proveedor no lo publica en GET /models, "
        "el perfil del modelo no trae `max_input_tokens` y no hay LLM_CONTEXT_TOKENS definido"
    )


def count_tokens(model: BaseChatModel, text: str) -> int:
    """Cuenta tokens con el tokenizador del modelo; error tipado si el modelo no lo soporta."""
    try:
        return model.get_num_tokens(text)
    except Exception as error:  # noqa: BLE001 - se re-tipa para no filtrar errores de libreria
        raise LLMProviderError(f"no se pudo contar tokens: {error}") from error
