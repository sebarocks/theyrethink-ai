"""Migrador de la Fase 5: reporte, idempotencia, fidelidad y memoria.

Las fixtures sintéticas construyen un `.db` con el esquema **viejo** (copiado del dump real),
porque el dump local tiene 0 conversaciones y no sirve para probar el migrador.
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agent.consolidation import FakeConsolidationQueue
from app.agent.dto import AgentContext
from app.agent.graph import build_chat_graph, build_memory_graph
from app.agent.service import AgentService
from app.models import Agent, KnowledgeSource, Role, Thread, User
from scripts.migrate_from_sqlite import migrate, read_legacy, split_legacy_memories
from tests.fakes import RecordingFakeLLM, fake_extractor

LEGACY_SCHEMA = """
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY, usuario TEXT NOT NULL, password_hash TEXT NOT NULL,
    rol TEXT NOT NULL, creado_en TEXT NOT NULL
);
CREATE TABLE roles (
    id INTEGER PRIMARY KEY, clave TEXT NOT NULL, nombre TEXT NOT NULL,
    descripcion TEXT NOT NULL, prompt TEXT NOT NULL, es_sistema INTEGER NOT NULL,
    creado_en TEXT NOT NULL, actualizado_en TEXT NOT NULL
);
CREATE TABLE agentes (
    id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, perfil TEXT NOT NULL,
    conocimiento TEXT NOT NULL, memoria TEXT NOT NULL, identidad_clave TEXT NOT NULL,
    identidad_custom TEXT NOT NULL, avatar_url TEXT NOT NULL, creado_en TEXT NOT NULL
);
CREATE TABLE fuentes_conocimiento (
    id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, contenido TEXT NOT NULL,
    creado_en TEXT NOT NULL
);
CREATE TABLE agente_fuentes (agente_id INTEGER NOT NULL, fuente_id INTEGER NOT NULL);
CREATE TABLE sesiones_chat (
    id INTEGER PRIMARY KEY, agente_id INTEGER NOT NULL, titulo TEXT NOT NULL,
    creado_en TEXT NOT NULL, actualizado_en TEXT NOT NULL
);
CREATE TABLE conversaciones (
    id INTEGER PRIMARY KEY, agente_id INTEGER NOT NULL, sesion_id INTEGER,
    fecha TEXT NOT NULL, hora TEXT NOT NULL, rol TEXT NOT NULL, mensaje TEXT NOT NULL
);
"""

MEMORY = "Vive en Santiago de Chile\n\n- Le gusta el café\n- Trabaja de noche"


def make_legacy_db(path: Path) -> Path:
    """Crea un `.db` heredado con datos fabricados (usuarios, roles, agentes y 1 conversación)."""
    connection = sqlite3.connect(path)
    try:
        connection.executescript(LEGACY_SCHEMA)
        connection.execute(
            "INSERT INTO usuarios VALUES (1,'admin','scrypt:32768:8:1$salt$hash','admin',"
            "'2026-01-01 10:00:00')"
        )
        connection.executemany(
            "INSERT INTO roles VALUES (?,?,?,?,?,?,?,?)",
            [
                (1, "basic", "Básico", "desc", "prompt basic", 1, "2026-01-01", "2026-01-01"),
                (
                    2,
                    "principito",
                    "Principito",
                    "desc",
                    "prompt principito",
                    1,
                    "2026-01-01",
                    "2026-01-01",
                ),
            ],
        )
        connection.executemany(
            "INSERT INTO fuentes_conocimiento VALUES (?,?,?,?)",
            [
                (1, "fuente_a", "contenido A", "2026-01-01"),
                (2, "fuente_b", "contenido B", "2026-01-01"),
            ],
        )
        connection.executemany(
            "INSERT INTO agentes VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    1,
                    "agente_uno",
                    "perfil uno",
                    "",
                    MEMORY,
                    "principito",
                    "",
                    "https://example.com/a.png",
                    "2026-01-01",
                ),
                (2, "agente_dos", "perfil dos", "", "", "rol_inexistente", "", "", "2026-01-01"),
            ],
        )
        connection.executemany(
            "INSERT INTO agente_fuentes VALUES (?,?)",
            [(1, 1), (2, 2), (99, 1)],  # (99,1) es huérfano a propósito
        )
        connection.executemany(
            "INSERT INTO sesiones_chat VALUES (?,?,?,?,?)",
            [
                (1, 1, "Charla con uno", "2026-02-01 09:00:00", "2026-02-01 09:05:00"),
                (2, 2, "Charla con dos", "2026-02-02 09:00:00", "2026-02-02 09:05:00"),
            ],
        )
        connection.executemany(
            "INSERT INTO conversaciones VALUES (?,?,?,?,?,?,?)",
            [
                (1, 1, 1, "2026-02-01", "09:00:00", "user", "Hola, me llamo Ana"),
                (2, 1, 1, "2026-02-01", "09:00:05", "assistant", "Hola Ana"),
                (3, 1, 1, "2026-02-01", "09:01:00", "user", "¿Te acuerdas?"),
                (4, 1, 1, "2026-02-01", "09:01:05", "assistant", "Sí, Ana"),
                (5, 2, 2, "2026-02-02", "09:00:00", "usuario", "Buena tarde"),
                (6, 2, 2, "2026-02-02", "09:00:05", "asistente", "Buena tarde"),
            ],
        )
        connection.commit()
    finally:
        connection.close()
    return path


def _service(sessionmaker: async_sessionmaker) -> AgentService:
    store = InMemoryStore()
    checkpointer = InMemorySaver()

    async def _load_context(agent_id: int) -> AgentContext:
        return AgentContext(
            agent_id=agent_id, name="x", profile="", identity_prompt="Eres un asistente."
        )

    chat = build_chat_graph(
        llm=RecordingFakeLLM(),
        store=store,
        load_context=_load_context,
        context_tokens=1_000,
        count_tokens=lambda _text: 1,
        checkpointer=checkpointer,
    )
    return AgentService(
        chat_graph=chat,
        memory_graph=build_memory_graph(extractor=fake_extractor(), store=store),
        store=store,
        checkpointer=checkpointer,
        queue=FakeConsolidationQueue(),
        sessionmaker=sessionmaker,
        llm=RecordingFakeLLM(),
        count_tokens=lambda _text: 1,
    )


def test_split_legacy_memories_ports_the_legacy_format() -> None:
    assert split_legacy_memories(MEMORY) == [
        "Vive en Santiago de Chile",
        "Le gusta el café",
        "Trabaja de noche",
    ]
    assert split_legacy_memories("") == []


async def test_dry_run_reports_without_writing(
    tmp_path: Path, isolated_sessionmaker: async_sessionmaker
) -> None:
    snapshot = read_legacy(make_legacy_db(tmp_path / "legacy.db"))

    report = await migrate(snapshot, isolated_sessionmaker, service=None, dry_run=True)  # type: ignore[arg-type]

    assert report.dry_run is True
    assert report.legacy_counts["usuarios"] == 1
    assert report.legacy_counts["agentes"] == 2
    assert report.legacy_counts["sesiones"] == 2
    assert report.legacy_counts["mensajes"] == 6
    assert report.actions.get("roles_nuevos") == 2
    assert report.actions.get("agentes_nuevos") == 2
    assert any("huérfano" in note for note in report.notes)

    async with isolated_sessionmaker() as session:
        assert (await session.execute(select(User))).scalars().all() == []


async def test_migration_is_idempotent_and_faithful(
    tmp_path: Path, isolated_sessionmaker: async_sessionmaker
) -> None:
    snapshot = read_legacy(make_legacy_db(tmp_path / "legacy.db"))
    service = _service(isolated_sessionmaker)

    first = await migrate(
        snapshot, isolated_sessionmaker, service, owner_username="admin", admin_email="a@b.co"
    )
    second = await migrate(snapshot, isolated_sessionmaker, service)

    # Idempotencia: la segunda corrida no crea nada nuevo.
    assert first.actions.get("hilos_creados") == 2
    assert second.actions.get("hilos_creados", 0) == 0
    assert second.actions.get("transcripts_importados", 0) == 0
    assert second.actions.get("transcripts_ya_presentes") == 2
    assert second.actions.get("agentes_creados", 0) == 0
    assert second.actions.get("roles_creados", 0) == 0

    async with isolated_sessionmaker() as session:
        users = (await session.execute(select(User))).scalars().all()
        roles = {role.key for role in (await session.execute(select(Role))).scalars()}
        agents = {agent.name: agent for agent in (await session.execute(select(Agent))).scalars()}
        sources = {
            source.name for source in (await session.execute(select(KnowledgeSource))).scalars()
        }
        threads = (await session.execute(select(Thread))).scalars().all()

    assert [user.username for user in users] == ["admin"]
    assert users[0].email == "a@b.co"
    assert users[0].password_hash.startswith("scrypt:")  # no se reescribe en la migración
    assert roles == {"basic", "principito"}
    assert sources == {"fuente_a", "fuente_b"}
    assert agents["agente_uno"].role_key == "principito"
    # `identidad_clave` inexistente se descarta y se reporta.
    assert agents["agente_dos"].role_key is None
    assert len(threads) == 2
    # Los hilos nacen consolidados: la memoria ya viene de `agentes.memoria`.
    assert all(thread.last_consolidated_message_count > 0 for thread in threads)

    # Fidelidad del transcript reconstruido.
    thread_uno = next(thread for thread in threads if thread.title == "Charla con uno")
    transcript = await service.read_messages(thread_id=thread_uno.id)
    assert [(message.role, message.text) for message in transcript] == [
        ("user", "Hola, me llamo Ana"),
        ("assistant", "Hola Ana"),
        ("user", "¿Te acuerdas?"),
        ("assistant", "Sí, Ana"),
    ]
    thread_dos = next(thread for thread in threads if thread.title == "Charla con dos")
    assert [m.role for m in await service.read_messages(thread_id=thread_dos.id)] == [
        "user",
        "assistant",
    ]


async def test_memory_is_migrated_to_the_store(
    tmp_path: Path, isolated_sessionmaker: async_sessionmaker
) -> None:
    snapshot = read_legacy(make_legacy_db(tmp_path / "legacy.db"))
    service = _service(isolated_sessionmaker)

    report = await migrate(snapshot, isolated_sessionmaker, service)

    async with isolated_sessionmaker() as session:
        agent_uno = (
            await session.execute(select(Agent).where(Agent.name == "agente_uno"))
        ).scalar_one()
        user = (await session.execute(select(User))).scalar_one()
    facts = await service.read_memory(agent_id=agent_uno.id, user_id=user.id)

    assert report.actions.get("hechos_memoria_escritos") == 3
    assert sorted(fact.content for fact in facts) == [
        "Le gusta el café",
        "Trabaja de noche",
        "Vive en Santiago de Chile",
    ]


def test_snapshot_reports_orphans_and_collisions(tmp_path: Path) -> None:
    path = make_legacy_db(tmp_path / "legacy.db")
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "INSERT INTO agentes VALUES (3,'agente_uno','p','','','basic','','','2026-01-01')"
        )
        connection.commit()
    finally:
        connection.close()

    snapshot = read_legacy(path)

    assert any("agente_fuentes" in orphan for orphan in snapshot.orphans)
    assert any("duplicado" in collision for collision in snapshot.collisions)
    assert any("no existe como rol" in discard for discard in snapshot.discards)


def test_legacy_message_roles_are_normalized(tmp_path: Path) -> None:
    snapshot = read_legacy(make_legacy_db(tmp_path / "legacy.db"))
    session_uno = next(item for item in snapshot.sessions if item.legacy_id == 1)
    session_dos = next(item for item in snapshot.sessions if item.legacy_id == 2)

    assert [message.role for message in session_uno.messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    # 'usuario'/'asistente' también se normalizan.
    assert [message.role for message in session_dos.messages] == ["user", "assistant"]
