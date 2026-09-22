"""Exporta el contrato OpenAPI generado por FastAPI a un archivo versionado."""

import json
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "openapi.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI exportado a {OUTPUT}")


if __name__ == "__main__":
    main()
