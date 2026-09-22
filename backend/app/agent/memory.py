"""Memoria nativa: hechos por `(agente, usuario)` en el `Store` de LangGraph (D1, D7).

Reglas que este modulo hace cumplir:

- **Namespace** `("agent", str(agent_id), "user", str(user_id))`. Las etiquetas del `Store`
  **deben ser cadenas**: con enteros LangGraph lanza `InvalidNamespaceError` (spike S2).
- **Hechos direccionables**, no un blob: un item por hecho, con clave derivada del contenido
  normalizado (la misma clave hace el `aput` idempotente).
- **Deduplicacion normalizada** antes de persistir.
- **Orden de insercion** preservado al leer (por `created_at`), sin reordenar al escribir:
  reordenar rompe la cache de prefijo (D7).
- **Techo de inyeccion** `0.4 × contexto_del_modelo`, calculado en runtime, nunca hardcodeado.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Sequence

from langgraph.store.base import BaseStore
from pydantic import BaseModel

__all__ = [
    "MEMORY_CONTEXT_FRACTION",
    "ExtractedMemories",
    "MemoryFact",
    "deduplicate_facts",
    "fact_key",
    "injection_budget_tokens",
    "memory_namespace",
    "normalize_fact",
    "read_facts",
    "select_injectable_facts",
    "write_facts",
]

# Fraccion del contexto reservada a la memoria inyectada (D7, §4 hueco 11).
MEMORY_CONTEXT_FRACTION = 0.4

# Tamano de pagina al recorrer el namespace del `Store`.
_PAGE_SIZE = 100


class MemoryFact(BaseModel):
    """Hecho persistente sobre el usuario."""

    content: str
    category: str | None = None


class ExtractedMemories(BaseModel):
    """Salida estructurada del extractor (D7): la forma la impone este esquema."""

    facts: list[MemoryFact]


def memory_namespace(agent_id: int, user_id: int) -> tuple[str, str, str, str]:
    """Namespace de memoria aislado por cuenta (D1/D6). Etiquetas siempre `str` (spike S2)."""
    return ("agent", str(agent_id), "user", str(user_id))


def normalize_fact(content: str) -> str:
    """Normaliza para deduplicar: espacios colapsados y sin distinguir mayusculas."""
    return " ".join(content.split()).casefold()


def fact_key(content: str) -> str:
    """Clave estable derivada del contenido normalizado.

    Repetir el mismo hecho reescribe la misma clave, asi que el `aput` es idempotente incluso
    si la dedup previa fallara.
    """
    return hashlib.sha256(normalize_fact(content).encode("utf-8")).hexdigest()[:32]


def deduplicate_facts(
    new_facts: Iterable[MemoryFact],
    existing_facts: Sequence[MemoryFact] = (),
) -> list[MemoryFact]:
    """Descarta hechos vacios o equivalentes normalizados a los ya existentes.

    Tambien deduplica dentro de `new_facts`, preservando el orden de aparicion.
    """
    seen = {normalize_fact(fact.content) for fact in existing_facts}
    result: list[MemoryFact] = []
    for fact in new_facts:
        key = normalize_fact(fact.content)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(fact)
    return result


def injection_budget_tokens(context_tokens: int) -> int:
    """Techo de inyeccion: `0.4 × contexto` (D7). El 60% restante queda para historial y salida."""
    return int(context_tokens * MEMORY_CONTEXT_FRACTION)


def select_injectable_facts(
    facts: Sequence[MemoryFact],
    *,
    budget_tokens: int,
    count_tokens: Callable[[str], int],
) -> list[MemoryFact]:
    """Toma hechos en orden de insercion hasta agotar el techo.

    Sin seleccion por relevancia (D7): es un prefijo codicioso y determinista. Si un hecho no
    cabe, se detiene — no se reordena ni se recorta el contenido.
    """
    selected: list[MemoryFact] = []
    used = 0
    for fact in facts:
        cost = count_tokens(fact.content)
        if used + cost > budget_tokens:
            break
        selected.append(fact)
        used += cost
    return selected


async def _search_all(store: BaseStore, namespace: tuple[str, ...]) -> list:
    """Recorre el namespace completo paginando (`asearch` tiene limite por defecto)."""
    items: list = []
    offset = 0
    while True:
        page = await store.asearch(namespace, limit=_PAGE_SIZE, offset=offset)
        items.extend(page)
        if len(page) < _PAGE_SIZE:
            return items
        offset += _PAGE_SIZE


async def read_facts(store: BaseStore, namespace: tuple[str, ...]) -> list[MemoryFact]:
    """Lee los hechos del namespace en orden de insercion (`created_at`, luego clave)."""
    items = await _search_all(store, namespace)
    items.sort(key=lambda item: (item.created_at, item.key))
    return [
        MemoryFact(content=item.value["content"], category=item.value.get("category"))
        for item in items
    ]


async def write_facts(
    store: BaseStore,
    namespace: tuple[str, ...],
    facts: Iterable[MemoryFact],
) -> list[MemoryFact]:
    """Persiste hechos nuevos tras deduplicar contra los existentes. Devuelve los escritos."""
    existing = await read_facts(store, namespace)
    new_facts = deduplicate_facts(facts, existing)
    for fact in new_facts:
        await store.aput(
            namespace,
            fact_key(fact.content),
            {"content": fact.content, "category": fact.category},
        )
    return new_facts
