"""Tests de la memoria: namespace, dedup, techo de inyeccion y `Store` (sin I/O real)."""

from langgraph.store.memory import InMemoryStore

from app.agent.memory import (
    MEMORY_CONTEXT_FRACTION,
    MemoryFact,
    deduplicate_facts,
    fact_key,
    injection_budget_tokens,
    memory_namespace,
    normalize_fact,
    read_facts,
    select_injectable_facts,
    write_facts,
)


def test_namespace_labels_are_strings() -> None:
    """Con enteros LangGraph lanza `InvalidNamespaceError` (spike S2)."""
    namespace = memory_namespace(1, 2)
    assert namespace == ("agent", "1", "user", "2")
    assert all(isinstance(label, str) for label in namespace)


def test_normalize_fact_collapses_and_lowercases() -> None:
    assert normalize_fact("  Vive   en\nSantiago ") == "vive en santiago"


def test_fact_key_is_deterministic_and_normalized() -> None:
    assert fact_key("Vive en Santiago") == fact_key("  vive   en santiago  ")


def test_deduplicate_facts_against_existing_and_within_new() -> None:
    existing = [MemoryFact(content="vive en Santiago")]
    new = [
        MemoryFact(content="Vive en Santiago"),  # duplicado normalizado del existente
        MemoryFact(content="trabaja en Music Pro"),
        MemoryFact(content="Trabaja en Music Pro"),  # duplicado dentro de `new`
        MemoryFact(content="   "),  # vacio
    ]
    result = deduplicate_facts(new, existing)
    assert [fact.content for fact in result] == ["trabaja en Music Pro"]


def test_injection_budget_is_forty_percent() -> None:
    assert MEMORY_CONTEXT_FRACTION == 0.4
    assert injection_budget_tokens(1_000_000) == 400_000
    assert injection_budget_tokens(128_000) == 51_200


def test_select_injectable_facts_respects_budget_and_order() -> None:
    facts = [MemoryFact(content=word) for word in ("uno", "dos", "tres")]
    selected = select_injectable_facts(facts, budget_tokens=2, count_tokens=lambda _text: 1)
    assert [fact.content for fact in selected] == ["uno", "dos"]


def test_select_injectable_facts_stops_at_first_that_does_not_fit() -> None:
    facts = [MemoryFact(content="grande"), MemoryFact(content="pequeno")]
    costs = {"grande": 10, "pequeno": 1}
    selected = select_injectable_facts(
        facts, budget_tokens=5, count_tokens=lambda text: costs[text]
    )
    assert selected == []


async def test_write_facts_deduplicates_and_is_idempotent() -> None:
    store = InMemoryStore()
    namespace = memory_namespace(1, 1)

    written = await write_facts(store, namespace, [MemoryFact(content="vive en Santiago")])
    assert [fact.content for fact in written] == ["vive en Santiago"]

    again = await write_facts(store, namespace, [MemoryFact(content="Vive en Santiago")])
    assert again == []

    facts = await read_facts(store, namespace)
    assert [fact.content for fact in facts] == ["vive en Santiago"]


async def test_memory_is_isolated_per_user() -> None:
    store = InMemoryStore()
    await write_facts(store, memory_namespace(1, 1), [MemoryFact(content="de alice")])
    await write_facts(store, memory_namespace(1, 2), [MemoryFact(content="de bob")])

    alice = await read_facts(store, memory_namespace(1, 1))
    bob = await read_facts(store, memory_namespace(1, 2))
    assert [fact.content for fact in alice] == ["de alice"]
    assert [fact.content for fact in bob] == ["de bob"]


async def test_read_facts_preserves_insertion_order() -> None:
    store = InMemoryStore()
    namespace = memory_namespace(7, 7)
    for content in ("primero", "segundo", "tercero"):
        await write_facts(store, namespace, [MemoryFact(content=content)])

    facts = await read_facts(store, namespace)
    assert [fact.content for fact in facts] == ["primero", "segundo", "tercero"]
