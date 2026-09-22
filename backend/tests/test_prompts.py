"""Tests *golden* de los prompts (funciones puras, sin I/O)."""

from app.agent.prompts import (
    CONCISION_RULES,
    SourceText,
    build_memory_block,
    build_memory_extraction_prompt,
    build_system_prompt,
    process_identity,
    resolve_identity_prompt,
    resolve_person_name,
)


def test_resolve_person_name_reads_profile_marker() -> None:
    profile = "NOMBRE:\nAlbert Einstein\n\nPROFESIÓN:\nFísico."
    assert resolve_person_name("albert_einstein", profile) == "Albert Einstein"


def test_resolve_person_name_falls_back_to_agent_name() -> None:
    assert resolve_person_name("benjamin", "sin marcador") == "benjamin"


def test_process_identity_replaces_both_markers() -> None:
    identity = "Actúa como [____] experto en [información del documento]."
    result = process_identity(identity, "  Luis Paredes  ")
    assert result == (
        "Actúa como Luis Paredes experto en la información disponible en la base de conocimiento."
    )


def test_process_identity_uses_default_name_when_blank() -> None:
    assert process_identity("Hola [____]", "   ") == "Hola el tema de conversación"


def test_resolve_identity_prompt_precedence() -> None:
    assert (
        resolve_identity_prompt(custom_identity="custom", role_prompt="rol", default_prompt="def")
        == "custom"
    )
    assert (
        resolve_identity_prompt(custom_identity=None, role_prompt="rol", default_prompt="def")
        == "rol"
    )
    assert (
        resolve_identity_prompt(custom_identity="  ", role_prompt=None, default_prompt="def")
        == "def"
    )


def test_build_system_prompt_golden() -> None:
    prompt = build_system_prompt(
        identity_prompt="Eres un profesor.",
        profile="NOMBRE:\nAna",
        sources=[SourceText(name="Doc", content="Contenido.")],
    )
    assert prompt == (
        "Eres un profesor.\n"
        "\n"
        "PERFIL:\n"
        "NOMBRE:\n"
        "Ana\n"
        "\n"
        "BASE DE CONOCIMIENTO:\n"
        "[Doc]\n"
        "Contenido.\n"
        "\n"
        f"{CONCISION_RULES}"
    )


def test_build_system_prompt_without_sources() -> None:
    prompt = build_system_prompt(identity_prompt="Rol", profile="", sources=[])
    assert "BASE DE CONOCIMIENTO:\n(sin conocimientos previos)" in prompt


def test_build_system_prompt_is_byte_stable() -> None:
    """El prefijo `[system]` no puede cambiar entre turnos (D7)."""
    kwargs = {
        "identity_prompt": "Rol",
        "profile": "Perfil",
        "sources": [SourceText(name="A", content="a")],
    }
    assert build_system_prompt(**kwargs) == build_system_prompt(**kwargs)


def test_build_memory_block_empty_returns_empty_string() -> None:
    assert build_memory_block([]) == ""
    assert build_memory_block(["  ", ""]) == ""


def test_build_memory_block_preserves_insertion_order() -> None:
    block = build_memory_block(["primero", "segundo", "tercero"])
    assert block == "MEMORIA DEL USUARIO:\n- primero\n- segundo\n- tercero"


def test_build_memory_extraction_prompt_lists_existing_facts() -> None:
    prompt = build_memory_extraction_prompt(
        conversation="Usuario: hola\nAgente: hola",
        existing_facts=["vive en Santiago"],
    )
    assert "- vive en Santiago" in prompt
    assert "CONVERSACIÓN:\nUsuario: hola\nAgente: hola" in prompt


def test_build_memory_extraction_prompt_without_existing_facts() -> None:
    prompt = build_memory_extraction_prompt(conversation="x", existing_facts=[])
    assert "(sin memorias almacenadas)" in prompt
