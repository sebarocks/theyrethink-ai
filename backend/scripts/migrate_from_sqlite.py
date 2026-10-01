"""Migrador de la base SQLite heredada al esquema nuevo (Fase 5).

Lee `agentes.db` **siempre en modo solo lectura** y lo lleva a Postgres + checkpointer +
`Store` reutilizando la API publica del nucleo (`AgentService.import_transcript` y
`ensure_memory`): no escribe filas de conversacion ni de memoria a mano (AGENTS.md §3.3,
ADR `0023`).

Garantias:

- **Idempotente**: *upsert* por clave natural (usuario, rol, fuente, agente, hilo) y las
  conversaciones solo se importan si el hilo no tiene transcript. Dos corridas dejan lo mismo.
- **No pisa secretos**: el `password_hash` de un usuario existente no se reescribe (pudo
  re-hashearse a Argon2 en un login).
- **No pisa la consolidacion**: `last_consolidated_*` de un hilo existente no se toca.

Uso:

    uv run python -m scripts.migrate_from_sqlite --source ../theythink-ai/agentes.db --dry-run
    uv run python -m scripts.migrate_from_sqlite --source ../theythink-ai/agentes.db \\
        --admin-email admin@example.com

El reporte de reconciliacion (conteos, huerfanos, descartes y colisiones) se imprime al final
y, con `--report`, se escribe a un archivo.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import datetime as dt
import json
import logging
import re
import shutil
import sqlite3
from collections.abc import Iterable, Sequence
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.dto import MessageDTO
from app.agent.memory import MemoryFact
from app.agent.service import AgentService
from app.models import Agent, AgentSource, KnowledgeSource, Role, Thread, User

logger = logging.getLogger("migrate")

GOLDEN_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "seed" / "golden" / "canonical_state.json"
)
DEFAULT_MIGRATED_EMAIL_DOMAIN = "migrated.invalid"

# Roles del canal heredado que se consideran del usuario; el resto, del asistente.
_USER_ROLES = {"user", "usuario", "human", "humano"}


# --------------------------------------------------------------------------- modelo de origen


@dataclasses.dataclass(frozen=True)
class LegacyUser:
    username: str
    password_hash: str
    role: str
    created_at: dt.datetime | None


@dataclasses.dataclass(frozen=True)
class LegacyRole:
    key: str
    name: str
    description: str
    prompt: str
    is_system: bool


@dataclasses.dataclass(frozen=True)
class LegacySource:
    name: str
    content: str


@dataclasses.dataclass(frozen=True)
class LegacyAgent:
    name: str
    profile: str
    role_key: str | None
    custom_identity: str | None
    avatar_url: str | None
    memory: str
    source_names: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class LegacyMessage:
    role: str
    text: str


@dataclasses.dataclass(frozen=True)
class LegacySession:
    legacy_id: int
    agent_name: str
    title: str
    created_at: dt.datetime | None
    updated_at: dt.datetime | None
    messages: tuple[LegacyMessage, ...]


@dataclasses.dataclass(frozen=True)
class LegacySnapshot:
    source: Path
    users: tuple[LegacyUser, ...]
    roles: tuple[LegacyRole, ...]
    sources: tuple[LegacySource, ...]
    agents: tuple[LegacyAgent, ...]
    sessions: tuple[LegacySession, ...]
    orphans: tuple[str, ...] = ()
    discards: tuple[str, ...] = ()
    collisions: tuple[str, ...] = ()


# ------------------------------------------------------------------------------ lectura


def _parse_timestamp(value: object) -> dt.datetime | None:
    """Interpreta los timestamps de texto heredados como UTC."""
    text = str(value or "").strip()
    if not text:
        return None
    parsed: dt.datetime | None = None
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = dt.datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.UTC)


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def read_legacy(source: Path) -> LegacySnapshot:
    """Lee el `.db` heredado en modo solo lectura y lo normaliza a DTOs."""
    if not source.is_file():
        raise SystemExit(f"no existe el origen: {source}")
    connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    orphans: list[str] = []
    discards: list[str] = []
    collisions: list[str] = []
    try:
        for table in ("usuarios", "roles", "agentes", "fuentes_conocimiento", "sesiones_chat"):
            if not _table_exists(connection, table):
                raise SystemExit(f"el origen no tiene la tabla esperada: {table}")

        users = tuple(
            LegacyUser(
                username=str(row["usuario"]),
                password_hash=str(row["password_hash"]),
                role="admin" if str(row["rol"]).lower() == "admin" else "usuario",
                created_at=_parse_timestamp(row["creado_en"]),
            )
            for row in connection.execute("SELECT * FROM usuarios ORDER BY id")
        )
        _flag_duplicates(users, key=lambda user: user.username, label="usuario", into=collisions)

        roles = tuple(
            LegacyRole(
                key=str(row["clave"]),
                name=str(row["nombre"]),
                description=str(row["descripcion"] or ""),
                prompt=str(row["prompt"] or ""),
                is_system=bool(row["es_sistema"]),
            )
            for row in connection.execute("SELECT * FROM roles ORDER BY id")
        )
        _flag_duplicates(roles, key=lambda role: role.key, label="rol", into=collisions)
        role_keys = {role.key for role in roles}

        sources = tuple(
            LegacySource(name=str(row["nombre"]), content=str(row["contenido"] or ""))
            for row in connection.execute("SELECT * FROM fuentes_conocimiento ORDER BY id")
        )
        _flag_duplicates(sources, key=lambda item: item.name, label="fuente", into=collisions)

        source_ids = {
            row["id"]: row["nombre"]
            for row in connection.execute("SELECT id, nombre FROM fuentes_conocimiento")
        }
        agent_ids = {
            row["id"]: row["nombre"] for row in connection.execute("SELECT id, nombre FROM agentes")
        }
        session_ids = {row["id"] for row in connection.execute("SELECT id FROM sesiones_chat")}

        links: dict[int, list[str]] = {}
        for row in connection.execute("SELECT agente_id, fuente_id FROM agente_fuentes"):
            if row["agente_id"] not in agent_ids or row["fuente_id"] not in source_ids:
                orphans.append(
                    f"agente_fuentes(agente_id={row['agente_id']}, fuente_id={row['fuente_id']})"
                )
                continue
            links.setdefault(row["agente_id"], []).append(source_ids[row["fuente_id"]])

        agents = []
        for row in connection.execute("SELECT * FROM agentes ORDER BY id"):
            role_key = str(row["identidad_clave"] or "").strip() or None
            if role_key is not None and role_key not in role_keys:
                discards.append(
                    f"agente {row['nombre']}: identidad_clave={role_key!r} no existe como rol"
                )
                role_key = None
            memory = str(row["memoria"] or "")
            agents.append(
                LegacyAgent(
                    name=str(row["nombre"]),
                    profile=str(row["perfil"] or ""),
                    role_key=role_key,
                    custom_identity=str(row["identidad_custom"] or "") or None,
                    avatar_url=str(row["avatar_url"] or "") or None,
                    memory=memory,
                    source_names=tuple(sorted(links.get(row["id"], []))),
                )
            )
        agents = tuple(agents)
        _flag_duplicates(agents, key=lambda agent: agent.name, label="agente", into=collisions)

        sessions = []
        for row in connection.execute("SELECT * FROM sesiones_chat ORDER BY id"):
            if row["agente_id"] not in agent_ids:
                orphans.append(f"sesiones_chat(id={row['id']}) -> agente_id={row['agente_id']}")
                continue
            messages = _read_messages(connection, row["id"], session_ids, orphans, discards)
            sessions.append(
                LegacySession(
                    legacy_id=int(row["id"]),
                    agent_name=agent_ids[row["agente_id"]],
                    title=str(row["titulo"] or "Conversación"),
                    created_at=_parse_timestamp(row["creado_en"]),
                    updated_at=_parse_timestamp(row["actualizado_en"]),
                    messages=messages,
                )
            )
    finally:
        connection.close()

    return LegacySnapshot(
        source=source,
        users=users,
        roles=roles,
        sources=sources,
        agents=agents,
        sessions=tuple(sessions),
        orphans=tuple(orphans),
        discards=tuple(discards),
        collisions=tuple(collisions),
    )


def _read_messages(
    connection: sqlite3.Connection,
    session_id: int,
    session_ids: set[int],
    orphans: list[str],
    discards: list[str],
) -> tuple[LegacyMessage, ...]:
    if not _table_exists(connection, "conversaciones"):
        return ()
    rows = connection.execute(
        """
        SELECT * FROM conversaciones
        WHERE sesion_id = ?
        ORDER BY fecha, hora, id
        """,
        (session_id,),
    ).fetchall()
    messages: list[LegacyMessage] = []
    for row in rows:
        raw_role = str(row["rol"] or "").strip().lower()
        if raw_role in _USER_ROLES:
            role = "user"
        elif raw_role:
            role = "assistant"
        else:
            discards.append(f"conversacion(id={row['id']}): rol vacío")
            continue
        text = str(row["mensaje"] or "")
        if not text:
            discards.append(f"conversacion(id={row['id']}): mensaje vacío")
            continue
        messages.append(LegacyMessage(role=role, text=text))
    return tuple(messages)


def _flag_duplicates(items: Iterable[object], *, key, label: str, into: list[str]) -> None:
    seen: set[object] = set()
    for item in items:
        value = key(item)
        if value in seen:
            into.append(f"{label} duplicado en origen: {value!r}")
        seen.add(value)


# ------------------------------------------------------------------- memoria heredada


def split_legacy_memories(text: str) -> list[str]:
    """Port de `_dividir_memorias` (`basededatos.py`): separa la memoria en hechos."""
    memories: list[str] = []
    for block in re.split(r"\n\s*\n", str(text).strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        is_list = all(re.match(r"^[-*•\d.]+\)?\s*", line) for line in lines)
        if is_list:
            memories.extend(
                clean for line in lines if (clean := re.sub(r"^[-*•\d.]+\)?\s*", "", line))
            )
        else:
            memories.append(" ".join(lines))
    return memories


# ----------------------------------------------------------------------------- reporte


@dataclasses.dataclass
class MigrationReport:
    source: Path
    dry_run: bool
    legacy_counts: dict[str, int] = dataclasses.field(default_factory=dict)
    actions: dict[str, int] = dataclasses.field(default_factory=dict)
    notes: list[str] = dataclasses.field(default_factory=list)

    def bump(self, key: str, amount: int = 1) -> None:
        if amount:
            self.actions[key] = self.actions.get(key, 0) + amount

    def note(self, message: str) -> None:
        self.notes.append(message)

    def render(self) -> str:
        lines = [
            f"Origen: {self.source}",
            f"Modo: {'dry-run (sin cambios)' if self.dry_run else 'aplicado'}",
            "",
            "Conteos de origen:",
        ]
        lines.extend(f"  {key}: {value}" for key, value in sorted(self.legacy_counts.items()))
        lines.append("")
        lines.append("Acciones:")
        if self.actions:
            lines.extend(f"  {key}: {value}" for key, value in sorted(self.actions.items()))
        else:
            lines.append("  (ninguna)")
        if self.notes:
            lines.append("")
            lines.append("Notas:")
            lines.extend(f"  - {note}" for note in self.notes)
        return "\n".join(lines)


def _count_legacy(snapshot: LegacySnapshot, report: MigrationReport) -> None:
    report.legacy_counts = {
        "usuarios": len(snapshot.users),
        "roles": len(snapshot.roles),
        "fuentes": len(snapshot.sources),
        "agentes": len(snapshot.agents),
        "sesiones": len(snapshot.sessions),
        "mensajes": sum(len(session.messages) for session in snapshot.sessions),
        "agentes_con_memoria": sum(1 for agent in snapshot.agents if agent.memory.strip()),
    }


def _collect_anomalies(snapshot: LegacySnapshot, report: MigrationReport) -> None:
    for category, items in (
        ("huérfano", snapshot.orphans),
        ("descarte", snapshot.discards),
        ("colisión", snapshot.collisions),
    ):
        for item in items:
            report.note(f"{category}: {item}")
        report.bump(f"{category}s", len(items))


# ------------------------------------------------------------------------------- aplicar


async def _analyze(snapshot: LegacySnapshot, sessionmaker, report: MigrationReport) -> None:
    """Dry-run: cuenta qué se crearía y qué se actualizaría, sin tocar nada."""
    async with sessionmaker() as session:
        role_keys = set((await session.execute(select(Role.key))).scalars())
        source_names = set((await session.execute(select(KnowledgeSource.name))).scalars())
        agent_names = set((await session.execute(select(Agent.name))).scalars())
        usernames = set((await session.execute(select(User.username))).scalars())
        thread_keys = {
            (row.user_id, row.agent_id, row.title, row.created_at)
            for row in (await session.execute(select(Thread))).scalars()
        }

    report.bump("roles_nuevos", sum(1 for r in snapshot.roles if r.key not in role_keys))
    report.bump("roles_existentes", sum(1 for r in snapshot.roles if r.key in role_keys))
    report.bump("fuentes_nuevas", sum(1 for s in snapshot.sources if s.name not in source_names))
    report.bump("agentes_nuevos", sum(1 for a in snapshot.agents if a.name not in agent_names))
    report.bump("usuarios_nuevos", sum(1 for u in snapshot.users if u.username not in usernames))
    report.bump("sesiones_a_importar", len(snapshot.sessions))
    report.bump("hilos_en_destino", len(thread_keys))
    report.note("dry-run: no se escribió nada")


async def migrate(
    snapshot: LegacySnapshot,
    sessionmaker: async_sessionmaker[AsyncSession],
    service: AgentService,
    *,
    dry_run: bool = False,
    owner_username: str | None = None,
    admin_email: str | None = None,
) -> MigrationReport:
    """Ejecuta (o simula) la migracion completa. Devuelve el reporte de reconciliacion."""
    report = MigrationReport(source=snapshot.source, dry_run=dry_run)
    _count_legacy(snapshot, report)
    _collect_anomalies(snapshot, report)

    if dry_run:
        await _analyze(snapshot, sessionmaker, report)
        await _compare_golden(snapshot, report)
        return report

    owner = _pick_owner(snapshot, owner_username)
    if owner is None:
        raise SystemExit("no se pudo determinar el usuario propietario (usa --owner)")

    domain = await _migrate_domain(snapshot, sessionmaker, owner, admin_email, report)
    await _migrate_conversations(snapshot, domain, sessionmaker, service, report)
    await _migrate_memory(snapshot, domain, service, report)
    await _compare_golden(snapshot, report)
    return report


def _pick_owner(snapshot: LegacySnapshot, owner_username: str | None) -> LegacyUser | None:
    if owner_username is not None:
        return next((u for u in snapshot.users if u.username == owner_username), None)
    if len(snapshot.users) == 1:
        return snapshot.users[0]
    return next((u for u in snapshot.users if u.role == "admin"), None)


@dataclasses.dataclass
class _DomainMap:
    """Ids del destino por clave natural, para las fases de checkpointer y `Store`."""

    user_ids: dict[str, int] = dataclasses.field(default_factory=dict)
    source_ids: dict[str, int] = dataclasses.field(default_factory=dict)
    agent_ids: dict[str, int] = dataclasses.field(default_factory=dict)
    thread_ids: dict[int, int] = dataclasses.field(default_factory=dict)


async def _migrate_domain(
    snapshot: LegacySnapshot,
    sessionmaker: async_sessionmaker[AsyncSession],
    owner: LegacyUser,
    admin_email: str | None,
    report: MigrationReport,
) -> _DomainMap:
    domain = _DomainMap()
    async with sessionmaker() as session:
        for legacy in snapshot.users:
            user = await _upsert_user(session, legacy, owner, admin_email, report)
            domain.user_ids[legacy.username] = int(user.id)
        for legacy in snapshot.roles:
            await _upsert_role(session, legacy, report)
        await session.flush()

        for legacy in snapshot.sources:
            source = await _upsert_source(session, legacy, report)
            domain.source_ids[legacy.name] = int(source.id)
        await session.flush()

        for legacy in snapshot.agents:
            agent = await _upsert_agent(session, legacy, domain, report)
            domain.agent_ids[legacy.name] = int(agent.id)
        await session.flush()

        owner_id = domain.user_ids[owner.username]
        for legacy in snapshot.sessions:
            thread = await _upsert_thread(session, legacy, owner_id, domain, report)
            if thread is not None:
                domain.thread_ids[legacy.legacy_id] = int(thread.id)

        await session.commit()
    return domain


async def _upsert_user(
    session: AsyncSession,
    legacy: LegacyUser,
    owner: LegacyUser,
    admin_email: str | None,
    report: MigrationReport,
) -> User:
    found = (
        await session.execute(select(User).where(User.username == legacy.username))
    ).scalar_one_or_none()
    if found is not None:
        # No se reescribe el hash: pudo re-hashearse a Argon2 en un login (ADR 0023).
        if (
            legacy.username == owner.username
            and admin_email
            and found.email.endswith(f"@{DEFAULT_MIGRATED_EMAIL_DOMAIN}")
        ):
            found.email = admin_email
        report.bump("usuarios_existentes")
        return found

    email = (
        admin_email
        if legacy.username == owner.username and admin_email
        else f"{legacy.username}@{DEFAULT_MIGRATED_EMAIL_DOMAIN}"
    )
    user = User(
        username=legacy.username,
        email=email,
        password_hash=legacy.password_hash,
        role=legacy.role,
        created_at=legacy.created_at or dt.datetime.now(dt.UTC),
    )
    session.add(user)
    await session.flush()
    report.bump("usuarios_creados")
    if legacy.username == owner.username and not admin_email:
        report.note(f"usuario {legacy.username}: sin --admin-email, se sintetiza {email}")
    return user


async def _upsert_role(session: AsyncSession, legacy: LegacyRole, report: MigrationReport) -> Role:
    role = (await session.execute(select(Role).where(Role.key == legacy.key))).scalar_one_or_none()
    if role is None:
        role = Role(key=legacy.key)
        session.add(role)
        report.bump("roles_creados")
    else:
        report.bump("roles_actualizados")
    role.name = legacy.name
    role.description = legacy.description
    role.prompt = legacy.prompt
    role.is_system = legacy.is_system
    return role


async def _upsert_source(
    session: AsyncSession, legacy: LegacySource, report: MigrationReport
) -> KnowledgeSource:
    source = (
        await session.execute(select(KnowledgeSource).where(KnowledgeSource.name == legacy.name))
    ).scalar_one_or_none()
    if source is None:
        source = KnowledgeSource(name=legacy.name)
        session.add(source)
        report.bump("fuentes_creadas")
    else:
        report.bump("fuentes_actualizadas")
    source.content = legacy.content
    await session.flush()
    return source


async def _upsert_agent(
    session: AsyncSession,
    legacy: LegacyAgent,
    domain: _DomainMap,
    report: MigrationReport,
) -> Agent:
    agent = (
        await session.execute(select(Agent).where(Agent.name == legacy.name))
    ).scalar_one_or_none()
    if agent is None:
        agent = Agent(name=legacy.name)
        session.add(agent)
        report.bump("agentes_creados")
    else:
        report.bump("agentes_actualizados")
    agent.profile = legacy.profile
    agent.role_key = legacy.role_key
    agent.custom_identity = legacy.custom_identity
    agent.avatar_url = legacy.avatar_url
    await session.flush()

    desired = {domain.source_ids[name] for name in legacy.source_names if name in domain.source_ids}
    rows = (
        await session.execute(select(AgentSource).where(AgentSource.agent_id == agent.id))
    ).scalars()
    existing = {row.source_id for row in rows}
    for source_id in existing - desired:
        await session.execute(
            delete(AgentSource).where(
                AgentSource.agent_id == agent.id, AgentSource.source_id == source_id
            )
        )
    for source_id in desired - existing:
        session.add(AgentSource(agent_id=agent.id, source_id=source_id))
    return agent


async def _upsert_thread(
    session: AsyncSession,
    legacy: LegacySession,
    owner_id: int,
    domain: _DomainMap,
    report: MigrationReport,
) -> Thread | None:
    agent_id = domain.agent_ids.get(legacy.agent_name)
    if agent_id is None:
        report.note(f"sesion {legacy.legacy_id}: agente {legacy.agent_name!r} no migrado")
        return None
    created_at = legacy.created_at or dt.datetime.now(dt.UTC)
    thread = (
        await session.execute(
            select(Thread).where(
                Thread.user_id == owner_id,
                Thread.agent_id == agent_id,
                Thread.title == legacy.title,
                Thread.created_at == created_at,
            )
        )
    ).scalar_one_or_none()
    last = legacy.messages[-1].text if legacy.messages else ""
    if thread is None:
        thread = Thread(
            agent_id=agent_id,
            user_id=owner_id,
            title=legacy.title,
            created_at=created_at,
            updated_at=legacy.updated_at or created_at,
            message_count=len(legacy.messages),
            last_preview=last[:200],
        )
        session.add(thread)
        await session.flush()
        report.bump("hilos_creados")
    else:
        report.bump("hilos_existentes")
    return thread


async def _migrate_conversations(
    snapshot: LegacySnapshot,
    domain: _DomainMap,
    sessionmaker: async_sessionmaker[AsyncSession],
    service: AgentService,
    report: MigrationReport,
) -> None:
    for legacy in snapshot.sessions:
        thread_id = domain.thread_ids.get(legacy.legacy_id)
        if thread_id is None or not legacy.messages:
            continue
        existing = await service.read_messages(thread_id=thread_id)
        if existing:
            report.bump("transcripts_ya_presentes")
            await _mark_consolidated(sessionmaker, thread_id, len(existing))
            continue
        await service.import_transcript(
            thread_id=thread_id,
            messages=[
                MessageDTO(role=message.role, text=message.text) for message in legacy.messages
            ],
        )
        report.bump("transcripts_importados")
        report.bump("mensajes_importados", len(legacy.messages))
        # La memoria de estos turnos ya viene de `agentes.memoria`: no se re-consolida.
        await _mark_consolidated(sessionmaker, thread_id, len(legacy.messages))


async def _mark_consolidated(
    sessionmaker: async_sessionmaker[AsyncSession], thread_id: int, position: int
) -> None:
    async with sessionmaker() as session:
        thread = await session.get(Thread, thread_id)
        if thread is None:
            return
        thread.last_consolidated_at = dt.datetime.now(dt.UTC)
        thread.last_consolidated_message_count = max(
            thread.last_consolidated_message_count, position
        )
        await session.commit()


async def _migrate_memory(
    snapshot: LegacySnapshot,
    domain: _DomainMap,
    service: AgentService,
    report: MigrationReport,
) -> None:
    """La memoria heredada era compartida por agente; se replica a cada usuario migrado."""
    for legacy in snapshot.agents:
        facts_text = split_legacy_memories(legacy.memory)
        if not facts_text:
            continue
        agent_id = domain.agent_ids.get(legacy.name)
        if agent_id is None:
            continue
        facts = [MemoryFact(content=content) for content in facts_text]
        for user_id in domain.user_ids.values():
            written = await service.ensure_memory(agent_id=agent_id, user_id=user_id, facts=facts)
            report.bump("hechos_memoria_escritos", len(written))
        report.bump("agentes_con_memoria_migrada")


async def _compare_golden(snapshot: LegacySnapshot, report: MigrationReport) -> None:
    """Contrasta el resultado con el golden de la Fase 1 y reporta diferencias."""
    if not GOLDEN_PATH.is_file():
        report.note(f"golden no encontrado: {GOLDEN_PATH}")
        return
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    checks = (
        ("roles", "key", {role.key for role in snapshot.roles}),
        ("agents", "name", {agent.name for agent in snapshot.agents}),
        ("sources", "name", {source.name for source in snapshot.sources}),
    )
    for section, field, migrated in checks:
        expected = {entry[field] for entry in golden.get(section, [])}
        missing = sorted(expected - migrated)
        extra = sorted(migrated - expected)
        report.note(
            f"golden {section}: {len(migrated)} migrados, {len(expected)} en golden, "
            f"{len(missing)} solo en golden, {len(extra)} solo migrados"
        )
        if extra:
            report.note(f"golden {section} extra: {', '.join(extra[:10])}")


# --------------------------------------------------------------------------------- CLI


def _backup(source: Path) -> Path:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = source.with_name(f"{source.name}.bak-{stamp}")
    shutil.copy2(source, destination)
    return destination


async def _run(args: argparse.Namespace) -> MigrationReport:
    from app.agent.runtime import agent_runtime
    from app.db import get_sessionmaker

    snapshot = read_legacy(Path(args.source))
    if args.dry_run:
        report = await migrate(
            snapshot,
            get_sessionmaker(),
            service=None,  # type: ignore[arg-type]  # dry-run no toca checkpointer
            dry_run=True,
            owner_username=args.owner,
            admin_email=args.admin_email,
        )
    else:
        backup = None if args.no_backup else _backup(Path(args.source))
        async with agent_runtime() as service:
            report = await migrate(
                snapshot,
                get_sessionmaker(),
                service,
                owner_username=args.owner,
                admin_email=args.admin_email,
            )
        if backup is not None:
            report.note(f"respaldo del origen: {backup}")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migra agentes.db al esquema nuevo (Fase 5).")
    parser.add_argument("--source", required=True, help="Ruta al agentes.db heredado.")
    parser.add_argument("--dry-run", action="store_true", help="Solo analiza y reporta.")
    parser.add_argument("--owner", help="Usuario propietario de los hilos migrados.")
    parser.add_argument("--admin-email", help="Correo sintetizado para el propietario.")
    parser.add_argument("--report", help="Escribe el reporte a este archivo.")
    parser.add_argument("--no-backup", action="store_true", help="No respalda el .db de origen.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    report = asyncio.run(_run(args))
    output = report.render()
    print(output)
    if args.report:
        Path(args.report).write_text(output + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
