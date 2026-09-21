"""Spike S1 — salida estructurada y streaming en un cliente OpenAI-compatible real.

Script **desechable**: su entregable es la conclusion escrita en
`docs/spikes/S1-structured-output-streaming.md`.

No conoce ningun proveedor concreto (D15): lee la configuracion del seam real,
`app.config.Settings`, es decir `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` del entorno o de
`backend/.env`. Si faltan, no ejecuta nada y lo dice. Nunca imprime la clave.

Separacion chat/extractor (S1):
- El **extractor** de memoria pide salida estructurada, y eso exige la respuesta completa
  para poder parsear y validar: se invoca con `streaming=False`.
- El **chat** (texto libre para una persona) si va con `streaming=True`, porque el valor ahi
  es ver los tokens llegar.

Salida: una linea por prueba y, al final, un **checklist de requisitos** para comparar
modelos de un vistazo.

Uso:

    uv run python -m scripts.spike_s1
    uv run python -m scripts.spike_s1 --model <modelo>
    uv run python -m scripts.spike_s1 --runs 5
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import get_settings

METHODS = ("json_schema", "function_calling", "json_mode")
MIN_CONTEXT = 1_000_000  # D15: "contexto amplio (1M deseable)"


class MemoryFact(BaseModel):
    content: str
    category: str | None = None


class ExtractedMemories(BaseModel):
    facts: list[MemoryFact]


CONVERSATION = """Conversación a extraer (hechos durativos sobre el usuario):

usuario: Hola, me llamo Ana y vivo en Santiago de Chile.
asistente: ¡Hola Ana! ¿En qué puedo ayudarte?
usuario: Trabajo como enfermera en turnos de noche y prefiero respuestas cortas.
asistente: Anotado.
usuario: Mi color favorito es el azul y odio el cilantro.
"""


def _require_settings():
    settings = get_settings()
    missing = [
        name
        for name, value in {
            "LLM_BASE_URL": settings.llm_base_url,
            "LLM_API_KEY": settings.llm_api_key,
            "LLM_MODEL": settings.llm_model,
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit("Faltan variables (entorno o backend/.env): " + ", ".join(missing))
    return settings


def _chat_model(temperature: float = 0.7, streaming: bool = True) -> ChatOpenAI:
    """Modelo de chat: texto libre para una persona, con streaming."""
    settings = _require_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        temperature=temperature,
        streaming=streaming,
    )


def _extractor(method: str) -> ChatOpenAI:
    """Extractor de memoria: salida estructurada, **sin streaming**.

    Con salida estructurada hay que esperar la respuesta completa para parsear y validar; el
    streaming no aporta y ademas es la ruta donde `langchain-openai` emite un warning de
    serializacion (v1.6.2). Ver S1.
    """
    settings = _require_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        # temperature=0,
        streaming=False,
    )


async def _extract(method: str) -> ExtractedMemories:
    extractor = _extractor(method).with_structured_output(ExtractedMemories, method=method)
    messages = [
        SystemMessage(content="Extrae los hechos durativos del usuario como JSON."),
        HumanMessage(content=CONVERSATION),
    ]
    return await extractor.ainvoke(messages)


async def test_streaming() -> dict[str, object]:
    llm = _chat_model()
    start = time.perf_counter()
    first_at: float | None = None
    chunks = 0
    async for chunk in llm.astream(
        [HumanMessage(content="Cuenta del 1 al 10 separado por comas.")]
    ):
        if chunk.content:
            if first_at is None:
                first_at = time.perf_counter() - start
            chunks += 1
    return {
        "ok": chunks > 1,
        "chunks": chunks,
        "ttft_s": round(first_at or -1, 3),
        "total_s": round(time.perf_counter() - start, 3),
    }


async def test_structured_method(method: str) -> dict[str, object]:
    start = time.perf_counter()
    try:
        result = await _extract(method)
    except Exception as error:  # noqa: BLE001 - el objetivo es clasificar el fallo
        return {"ok": False, "error": f"{type(error).__name__}: {error}"[:120]}
    return {
        "ok": True,
        "latency_s": round(time.perf_counter() - start, 3),
        "n_facts": len(result.facts),
        "sample": result.facts[0].content[:50] if result.facts else "",
    }


async def test_reliability(method: str, runs: int) -> dict[str, object]:
    valid = 0
    latencies: list[float] = []
    for _ in range(runs):
        start = time.perf_counter()
        try:
            result = await _extract(method)
        except Exception:  # noqa: BLE001
            continue
        latencies.append(time.perf_counter() - start)
        if result.facts:
            valid += 1
    return {
        "ok": valid == runs,
        "valid": valid,
        "runs": runs,
        "avg_latency_s": round(sum(latencies) / len(latencies), 3) if latencies else None,
    }


async def test_concurrency(method: str, n_extractions: int = 4) -> dict[str, object]:
    """Chat en streaming + extracciones en paralelo (extractor sin streaming)."""

    async def chat() -> int:
        count = 0
        async for chunk in _chat_model().astream(
            [HumanMessage(content="Escribe una frase sobre el mar.")]
        ):
            if chunk.content:
                count += 1
        return count

    start = time.perf_counter()
    chat_result, *extractions = await asyncio.gather(
        chat(), *[_extract(method) for _ in range(n_extractions)], return_exceptions=True
    )
    failures = sum(1 for e in extractions if isinstance(e, BaseException))
    facts = [len(e.facts) for e in extractions if isinstance(e, ExtractedMemories)]
    return {
        "ok": failures == 0 and isinstance(chat_result, int) and len(facts) == n_extractions,
        "chat_chunks": chat_result if isinstance(chat_result, int) else -1,
        "extractions_ok": len(facts),
        "extractions_failed": failures,
        "wall_s": round(time.perf_counter() - start, 3),
    }


async def test_system_message_in_middle() -> dict[str, object]:
    """D7 exige inyectar `system` (memoria) antes del mensaje nuevo."""
    try:
        message = await _chat_model(streaming=False).ainvoke(
            [
                HumanMessage(content="Hola"),
                SystemMessage(content="Responde SIEMPRE en mayúsculas."),
                HumanMessage(content="di hola"),
            ]
        )
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": f"{type(error).__name__}: {error}"[:120]}
    return {"ok": True, "sample": message.content[:30]}


async def test_prompt_cache() -> dict[str, object]:
    llm = _chat_model(streaming=False)
    prefix = "Contexto estable de prueba. " * 200
    cache_reads: list[int | None] = []
    for _ in range(2):
        message = await llm.ainvoke(
            [SystemMessage(content=prefix), HumanMessage(content="Responde ok.")]
        )
        usage = message.usage_metadata or {}
        cache_reads.append((usage.get("input_token_details") or {}).get("cache_read"))
    hit = cache_reads[1] or 0
    return {"ok": hit > 0, "cache_read_tokens": cache_reads}


async def get_model_info(model: str) -> dict[str, object]:
    """Resumen del modelo en `GET /models` (no se vuelca el listado completo)."""
    settings = _require_settings()
    base = str(settings.llm_base_url).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{base}/models")
        entries = response.json().get("data", [])
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": f"{type(error).__name__}: {error}"[:120]}

    match = next((m for m in entries if m.get("id") == model), None)
    if match is None:
        match = next(
            (m for m in entries if str(m.get("id", "")).endswith(model.split("/")[-1])), None
        )
    if match is None:
        return {"ok": False, "listed": len(entries), "found": False}
    context = int(match.get("context_length") or 0)
    return {
        "ok": context >= MIN_CONTEXT,
        "listed": len(entries),
        "found": True,
        "context_length": context,
        "max_completion_tokens": match.get("top_provider", {}).get("max_completion_tokens"),
    }


def _mark(ok: bool) -> str:
    return "OK  " if ok else "FALLA"


async def main() -> None:
    _require_settings()
    settings = get_settings()
    runs = int(os.environ.get("SPIKE_RUNS", "3"))

    print(f"model    = {settings.llm_model}")
    print(f"base_url = {settings.llm_base_url}")
    print()

    streaming = await test_streaming()
    print(
        f"[A] streaming (chat) ..... {_mark(bool(streaming['ok']))} "
        f"chunks={streaming['chunks']} ttft={streaming['ttft_s']}s total={streaming['total_s']}s"
    )

    structured: dict[str, dict[str, object]] = {}
    print("[B] salida estructurada (extractor sin streaming):")
    for method in METHODS:
        result = await test_structured_method(method)
        structured[method] = result
        if result["ok"]:
            print(
                f"    - {method:<15} {_mark(True)} {result['latency_s']}s facts={result['n_facts']}"
            )
        else:
            print(f"    - {method:<15} {_mark(False)} {result['error']}")

    working = [m for m in METHODS if structured[m]["ok"]]
    preferred = "json_schema" if "json_schema" in working else (working[0] if working else None)

    reliability: dict[str, dict[str, object]] = {}
    for method in working:
        reliability[method] = await test_reliability(method, runs)
        r = reliability[method]
        print(
            f"[C] fiabilidad {method:<15} {_mark(bool(r['ok']))} "
            f"{r['valid']}/{r['runs']} media={r['avg_latency_s']}s"
        )
    if not working:
        print("[C] fiabilidad ............ FALLA (ningun metodo estructurado funciona)")

    if preferred:
        concurrency = await test_concurrency(preferred)
        line = (
            f"[D] concurrencia ({preferred}) {_mark(bool(concurrency['ok']))} "
            f"chunks={concurrency['chat_chunks']} extracciones_ok={concurrency['extractions_ok']} "
            f"fallos={concurrency['extractions_failed']} pared={concurrency['wall_s']}s"
        )
        print(line)
    else:
        concurrency = {"ok": False}
        print("[D] concurrencia .......... FALLA (sin metodo estructurado)")

    system_middle = await test_system_message_in_middle()
    detail = system_middle.get("sample") or system_middle.get("error", "")
    print(f"[E] system en medio (D7) . {_mark(bool(system_middle['ok']))} {detail}")

    cache = await test_prompt_cache()
    reads = cache["cache_read_tokens"]
    print(f"[F] cache de prefijo (D7)  {_mark(bool(cache['ok']))} cache_read={reads}")

    info = await get_model_info(settings.llm_model)
    if info.get("found"):
        print(
            f"[G] contexto del modelo .. {_mark(bool(info['ok']))} "
            f"ctx={info['context_length']} max_out={info['max_completion_tokens']}"
        )
    else:
        print(f"[G] contexto del modelo .. FALLA (no listado; {info.get('listed', '?')} modelos)")

    methods_ok = {m: bool(reliability.get(m, {}).get("ok", False)) for m in METHODS}
    schema_enforced = methods_ok["json_schema"] or methods_ok["function_calling"]

    hard = {
        "streaming (chat)": bool(streaming["ok"]),
        "salida estructurada o tool calling (esquema impuesto)": schema_enforced,
        "concurrencia": bool(concurrency["ok"]),
        "system en medio (D7)": bool(system_middle["ok"]),
    }
    soft = {
        "cache de prefijo (D7)": bool(cache["ok"]),
        "contexto >= 1M (deseable)": bool(info.get("ok")),
    }

    print("\n== Requisitos duros (D15) ==")
    for name, ok in hard.items():
        print(f"  [{_mark(ok)}] {name}")
    print("== Condiciones adicionales ==")
    for name, ok in soft.items():
        print(f"  [{_mark(ok)}] {name}")
    print("== Metodos de salida estructurada (fiabilidad) ==")
    print(f"  [{_mark(methods_ok['json_schema'])}] json_schema      (esquema impuesto, preferido)")
    print(f"  [{_mark(methods_ok['function_calling'])}] function_calling (esquema impuesto)")
    print(f"  [{_mark(methods_ok['json_mode'])}] json_mode        (sin esquema; exige plan B)")

    structured_item = "salida estructurada o tool calling (esquema impuesto)"
    core_ok = all(value for key, value in hard.items() if key != structured_item)
    if not core_ok:
        verdict = "NO CUMPLE (falla un requisito base)"
    elif methods_ok["json_schema"]:
        verdict = "COMPLETO (salida estructurada con json_schema)"
    elif methods_ok["function_calling"]:
        verdict = "CUMPLE (tool calling; D15 lo acepta)"
    elif methods_ok["json_mode"]:
        verdict = "PARCIAL (solo json_object: requiere plan B con validacion propia)"
    else:
        verdict = "NO CUMPLE (sin salida estructurada fiable)"

    print(f"\nResultado: {verdict}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Spike S1 (agnostico de proveedor).")
    parser.add_argument("--model", help="Sobrescribe LLM_MODEL solo para esta corrida.")
    parser.add_argument(
        "--runs", type=int, default=3, help="Corridas de fiabilidad (por defecto 3)."
    )
    args = parser.parse_args()
    if args.model:
        os.environ["LLM_MODEL"] = args.model
    os.environ["SPIKE_RUNS"] = str(args.runs)
    asyncio.run(main())
