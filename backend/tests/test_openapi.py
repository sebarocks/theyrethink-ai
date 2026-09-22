"""El contrato OpenAPI versionado no puede cambiar accidentalmente."""

import json
from pathlib import Path

from app.main import app

SNAPSHOT = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def test_openapi_matches_versioned_snapshot() -> None:
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert app.openapi() == expected
