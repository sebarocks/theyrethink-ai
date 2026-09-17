"""Tests de configuración: las invariantes de seguridad tienen que ser verificables."""

import pytest
from pydantic import ValidationError

from app.config import Settings

VALID_DATABASE_URL = "postgresql+asyncpg://theyrethink:theyrethink@localhost:5432/theyrethink"


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "secret_key": "x" * 32,
        "database_url": VALID_DATABASE_URL,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_secret_key_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin SECRET_KEY la aplicación no debe poder construirse."""
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=VALID_DATABASE_URL)


def test_secret_key_has_a_minimum_length() -> None:
    with pytest.raises(ValidationError):
        _settings(secret_key="demasiado-corta")


def test_debug_defaults_to_false() -> None:
    assert _settings().debug is False


def test_debug_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError):
        _settings(environment="production", debug=True)


def test_debug_is_allowed_outside_production() -> None:
    assert _settings(environment="development", debug=True).debug is True


def test_database_url_must_be_postgres() -> None:
    """SQLite queda descartado por diseño (ADR 0003)."""
    with pytest.raises(ValidationError):
        _settings(database_url="sqlite:///./local.db")
