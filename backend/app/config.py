"""Configuración de la aplicación, cargada desde variables de entorno.

Regla de seguridad (AGENTS.md §5): no existen valores por defecto para secretos.
`SECRET_KEY` es obligatoria y debe tener al menos 32 caracteres.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "theyrethink-ai"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    # Sin valor por defecto a propósito: fallar al arrancar es mejor que arrancar inseguro.
    secret_key: str = Field(min_length=32)

    database_url: PostgresDsn

    # Cliente LLM (D15): endpoint OpenAI-compatible configurable por entorno.
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None

    # Primer administrador (D13). Sin contrasena por defecto: si `admin_password` no esta
    # definida, el seed omite la creacion y avisa (AGENTS.md §5).
    admin_username: str = "admin"
    admin_email: str | None = None
    admin_password: str | None = None

    @model_validator(mode="after")
    def _forbid_debug_in_production(self) -> "Settings":
        if self.environment == "production" and self.debug:
            raise ValueError("debug no puede estar activo en producción")
        return self


@lru_cache
def get_settings() -> Settings:
    """Instancia única de la configuración."""
    return Settings()
