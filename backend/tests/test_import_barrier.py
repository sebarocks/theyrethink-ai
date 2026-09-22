"""Segunda barrera de la costura (S5): `langgraph`/`langchain` solo dentro de `app/agent/`.

`import-linter` enumera los paquetes de primer nivel uno por uno, asi que un paquete nuevo
quedaria sin cubrir. Este test recorre el arbol de imports y falla si aparece la libreria
fuera de `app/agent/`.
"""

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
FORBIDDEN_ROOTS = {"langgraph", "langchain", "langchain_core", "langchain_openai"}


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_library_is_confined_to_agent_package() -> None:
    offenders: dict[str, set[str]] = {}
    for path in APP_DIR.rglob("*.py"):
        if "agent" in path.relative_to(APP_DIR).parts:
            continue
        forbidden = _imported_roots(path) & FORBIDDEN_ROOTS
        if forbidden:
            offenders[str(path.relative_to(APP_DIR))] = forbidden

    assert offenders == {}, f"imports de la libreria fuera de app/agent: {offenders}"
