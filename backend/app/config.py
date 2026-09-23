"""Configuración de la aplicación, cargada desde variables de entorno.

Regla de seguridad (AGENTS.md §5): no existen valores por defecto para secretos.
`SECRET_KEY` es obligatoria y debe tener al menos 32 caracteres.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

StructuredOutputMethod = Literal["json_schema", "function_calling"]


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
    # Contexto del modelo para el techo de memoria (D7). **Override opcional**: el contexto se
    # descubre en runtime desde `GET /models` del proveedor; esto solo hace falta para
    # proveedores que no lo publican (p. ej. la API de OpenAI).
    llm_context_tokens: int | None = None
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    # `json_schema` impone el esquema; `function_calling` es el fallback equivalente (S1).
    llm_structured_output_method: StructuredOutputMethod = "json_schema"

    # Cola de consolidacion de memoria (D7/D14).
    consolidation_worker_enabled: bool = True
    consolidation_interval_seconds: float = 1.0
    consolidation_max_attempts: int = 3

    # Primer administrador (D13). Sin contrasena por defecto: si `admin_password` no esta
    # definida, el seed omite la creacion y avisa (AGENTS.md §5).
    admin_username: str = "admin"
    admin_email: str | None = None
    admin_password: str | None = None

    # Avatares: volumen local fuera de los estáticos (ADR 0017).
    avatar_storage_dir: str = "var/avatars"

    # Build de la SPA que sirve FastAPI en el mismo origen (D4). Si está vacío, se usa
    # `frontend/build` del repo; si el directorio no existe, no se monta (modo desarrollo).
    frontend_dist_dir: str | None = None

    @model_validator(mode="after")
    def _forbid_debug_in_production(self) -> "Settings":
        if self.environment == "production" and self.debug:
            raise ValueError("debug no puede estar activo en producción")
        return self


@lru_cache
def get_settings() -> Settings:
    """Instancia única de la configuración."""
    return Settings()
