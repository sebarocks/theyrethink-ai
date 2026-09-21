"""Extractor puntual: porta los datos canonicos de `theythink-ai` a JSON.

Se ejecuta **una vez** durante la Fase 1 para producir `app/seed/data/canonical.json`
a partir del proyecto de referencia (solo lectura). No forma parte del runtime ni de la
suite de tests: es una herramienta de provenance.

Uso:

    uv run python scripts/port_canonical_seed.py ../theythink-ai

El JSON resultante contiene tres bloques: `roles`, `sources` y `agents`, normalizados al
esquema de `app/models/domain.py`. La asociacion N:M vive en `agents[].source_names`.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any


def load_assignments(path: Path) -> dict[str, Any]:
    """Devuelve las asignaciones de nivel superior del modulo, resolviendo nombres."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    namespace: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not names:
            continue
        try:
            value = ast.literal_eval(node.value)
        except ValueError:
            try:
                value = eval(  # noqa: S307 - repo de referencia de confianza, uso puntual
                    compile(ast.Expression(node.value), str(path), "eval"),
                    {"__builtins__": {}},
                    namespace,
                )
            except Exception:
                # Asignaciones no literales irrelevantes (p. ej. alias de clases).
                continue
        for name in names:
            namespace[name] = value
    return namespace


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build(reference: Path) -> dict[str, Any]:
    identidades = load_assignments(reference / "identidades.py")["IDENTIDADES"]
    seed = load_assignments(reference / "seed.py")
    personajes = load_assignments(reference / "basededatos.py")["PERSONAJES_CANONICOS"]
    empresa = load_assignments(reference / "empresa.py")["PERFILES_EMPRESA"]

    roles: list[dict[str, Any]] = []
    for key, data in identidades.items():
        roles.append(
            {
                "key": key,
                "name": data["name"],
                "description": data["description"],
                "prompt": data["prompt"],
                "is_system": True,
            }
        )

    sources: dict[str, str] = {}
    agents: list[dict[str, Any]] = []

    # 1. Agentes de ejemplo de `seed.py`, con sus bases de conocimiento propias.
    for base in seed["BASES_CONOCIMIENTO_EJEMPLO"]:
        sources[base["nombre"]] = base["contenido"]
    for ejemplo in seed["AGENTES_EJEMPLO"]:
        agents.append(
            {
                "name": ejemplo["nombre"],
                "profile": ejemplo["perfil"],
                "role_key": _clean(ejemplo.get("identidad_clave")),
                "custom_identity": _clean(ejemplo.get("identidad_custom")),
                "avatar_url": None,
                "source_names": list(ejemplo.get("bases", [])),
            }
        )

    # 2. Personajes canonicos de `basededatos.py`, cada uno con su fuente curada.
    for personaje in personajes:
        sources[personaje["fuente_nombre"]] = personaje["fuente_contenido"]
        agents.append(
            {
                "name": personaje["nombre"],
                "profile": personaje["perfil"],
                "role_key": _clean(personaje.get("identidad_clave")),
                "custom_identity": None,
                "avatar_url": _clean(personaje.get("avatar_url")),
                "source_names": [personaje["fuente_nombre"]],
            }
        )

    # 3. Perfiles de empresa de `empresa.py`. El legacy convertia el `conocimiento` del
    #    agente en una fuente con el nombre del propio agente (migrar_conocimientos_legacy),
    #    y esa es la forma canonica que preservamos aqui.
    for perfil in empresa:
        nombre = perfil["nombre"]
        sources[nombre] = perfil.get("conocimiento", "")
        agents.append(
            {
                "name": nombre,
                "profile": perfil["perfil"],
                "role_key": _clean(perfil.get("identidad_clave")),
                "custom_identity": _clean(perfil.get("identidad_custom")),
                "avatar_url": None,
                "source_names": [nombre],
            }
        )

    return {
        "roles": roles,
        "sources": [
            {"name": name, "content": content} for name, content in sorted(sources.items())
        ],
        "agents": sorted(agents, key=lambda a: a["name"]),
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("uso: port_canonical_seed.py <ruta-theythink-ai>")
    reference = Path(sys.argv[1]).resolve()
    destination = Path(__file__).resolve().parents[1] / "app" / "seed" / "data" / "canonical.json"
    data = build(reference)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"escrito {destination}: "
        f"{len(data['roles'])} roles, {len(data['sources'])} fuentes, {len(data['agents'])} agentes"
    )


if __name__ == "__main__":
    main()
