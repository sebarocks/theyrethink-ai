"""Construccion de prompts — **Python puro**, sin I/O ni dependencias de la libreria.

Heredero directo de `prompt.py` del proyecto de referencia, con dos cambios exigidos por
D7 (ADR `0013`):

1. **La memoria no forma parte del system prompt.** El orden canonico es
   `[system][historial][memoria][mensaje nuevo]`; la memoria se inyecta al final y de forma
   transitoria (`build_memory_block`), de modo que el prefijo `[system][historial]` quede
   byte-estable y cacheable.
2. **La extraccion de memoria es estructurada** (`with_structured_output`), no el truco
   `NO_MEMORIA` parseado como texto: aqui solo se construye la instruccion.

Todas las funciones son puras: reciben strings y devuelven un string. Se testean sin red ni
base de datos (AGENTS.md §6).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "CONCISION_RULES",
    "DEFAULT_PERSON_NAME",
    "DOCUMENT_MARKER",
    "DOCUMENT_REFERENCE",
    "MEMORY_BLOCK_HEADER",
    "NAME_MARKER",
    "SourceText",
    "build_memory_block",
    "build_memory_extraction_prompt",
    "build_system_prompt",
    "process_identity",
    "resolve_identity_prompt",
    "resolve_person_name",
]

# Marcadores dinamicos dentro de las identidades de rol (portados de `prompt.py`).
NAME_MARKER = "[____]"
DOCUMENT_MARKER = "[información del documento]"

DEFAULT_PERSON_NAME = "el tema de conversación"
DOCUMENT_REFERENCE = "la información disponible en la base de conocimiento"

# Directrices universales de brevedad y control de tokens (portadas de `prompt.py`).
CONCISION_RULES = """DIRECTRICES OBLIGATORIAS DE RESPUESTA Y CONTROL DE TOKENS:
- Responde de forma breve, clara y directa.
- Utiliza únicamente la información necesaria para responder.
- No repitas la pregunta.
- Evita introducciones, conclusiones y explicaciones innecesarias.
- Prioriza respuestas de 2 a 5 frases."""

MEMORY_BLOCK_HEADER = "MEMORIA DEL USUARIO:"

_EMPTY_KNOWLEDGE = "(sin conocimientos previos)"
_EMPTY_MEMORY = "(sin memorias almacenadas)"


@dataclass(frozen=True)
class SourceText:
    """Fuente de conocimiento ya resuelta, lista para el prompt."""

    name: str
    content: str


def resolve_person_name(agent_name: str, profile: str) -> str:
    """Extrae el nombre legible de la persona desde el perfil del agente.

    Port de `AgenteDB.obtener_nombre`: busca la linea `NOMBRE:` y devuelve la primera linea
    no vacia que la sigue; si no la encuentra, cae al nombre del agente.
    """
    lines = profile.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith("NOMBRE:"):
            for following in lines[index + 1 :]:
                if following.strip():
                    return following.strip()
    return agent_name


def process_identity(identity_prompt: str, person_name: str) -> str:
    """Sustituye los marcadores del prompt de identidad.

    `[____]` pasa a ser el nombre de la persona (o el tema de conversacion) y
    `[información del documento]` la referencia a la base de conocimiento.
    """
    name = person_name.strip() or DEFAULT_PERSON_NAME
    processed = identity_prompt.replace(NAME_MARKER, name)
    return processed.replace(DOCUMENT_MARKER, DOCUMENT_REFERENCE)


def resolve_identity_prompt(
    *,
    custom_identity: str | None,
    role_prompt: str | None,
    default_prompt: str,
) -> str:
    """Elige el prompt de identidad efectivo.

    Paridad con `info_identidad` del proyecto de referencia: la identidad personalizada del
    agente tiene precedencia sobre el rol, y el rol por defecto es el ultimo recurso.
    """
    if custom_identity and custom_identity.strip():
        return custom_identity
    if role_prompt and role_prompt.strip():
        return role_prompt
    return default_prompt


def _knowledge_text(sources: Sequence[SourceText]) -> str:
    """Ensambla las fuentes como bloques `[nombre]\\ncontenido` (port de `cargar_conocimiento`)."""
    parts: list[str] = []
    for source in sources:
        content = source.content.strip()
        if not content:
            continue
        name = source.name.strip()
        parts.append(f"[{name}]\n{content}" if name else content)
    return "\n\n".join(parts) if parts else _EMPTY_KNOWLEDGE


def build_system_prompt(
    *,
    identity_prompt: str,
    profile: str,
    sources: Sequence[SourceText] = (),
) -> str:
    """Construye el bloque `[system]` del prompt.

    **No incluye memoria** (D7): la memoria se inyecta al final y de forma transitoria. El
    resultado solo depende de la configuracion del agente, asi que es byte-estable entre
    turnos mientras esa configuracion no cambie — que es lo que habilita la cache de prefijo.
    """
    return f"""{identity_prompt}

PERFIL:
{profile.strip()}

BASE DE CONOCIMIENTO:
{_knowledge_text(sources)}

{CONCISION_RULES}"""


def build_memory_block(facts: Sequence[str]) -> str:
    """Construye el bloque de memoria transitorio que se inyecta antes del mensaje nuevo.

    Devuelve cadena vacia si no hay hechos: no inyectar nada mantiene el prompt limpio y no
    altera el tramo final cuando la memoria esta vacia. El orden de `facts` se respeta tal
    cual (orden de insercion, D7).
    """
    cleaned = [fact.strip() for fact in facts if fact and fact.strip()]
    if not cleaned:
        return ""
    bullets = "\n".join(f"- {fact}" for fact in cleaned)
    return f"{MEMORY_BLOCK_HEADER}\n{bullets}"


def build_memory_extraction_prompt(
    *,
    conversation: str,
    existing_facts: Sequence[str] = (),
) -> str:
    """Instruccion para el extractor de memoria (salida estructurada, D7).

    La forma la impone el esquema Pydantic via `with_structured_output`; aqui solo se fija el
    criterio. Se listan los hechos existentes para que el modelo no los repita (la dedup
    normalizada definitiva la hace `memory.py`).
    """
    existing = [fact.strip() for fact in existing_facts if fact and fact.strip()]
    memory_text = "\n".join(f"- {fact}" for fact in existing) if existing else _EMPTY_MEMORY
    return f"""Analiza la conversación y extrae hechos NUEVOS y RELEVANTES sobre el usuario que
merezcan recordarse en futuras conversaciones.

Solo debes devolver información que sea:
- útil
- persistente
- relevante para el usuario
- diferente de lo que ya existe en la memoria

Si no existe información nueva, devuelve una lista de hechos vacía.

MEMORIA ACTUAL:
{memory_text}

CONVERSACIÓN:
{conversation.strip()}"""
