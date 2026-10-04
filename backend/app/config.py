"""Configuración de la aplicación, cargada desde variables de entorno.

Regla de seguridad (AGENTS.md §5): no existen valores por defecto para secretos.
`SECRET_KEY` es obligatoria y debe tener al menos 32 caracteres.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator, model_validator
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

    # Observabilidad (D25, ADR 0028). `/metrics` está desactivado por defecto y, si se define
    # `metrics_token`, exige `Authorization: Bearer`.
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"
    metrics_enabled: bool = False
    metrics_token: str | None = None

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
    # Tiempo que un trabajo reclamado queda reservado antes de poder reclamarse de nuevo.
    consolidation_lease_seconds: float = 300.0

    # Primer administrador (D13). Sin contrasena por defecto: si `admin_password` no esta
    # definida, el seed omite la creacion y avisa (AGENTS.md §5).
    admin_username: str = "admin"
    admin_email: str | None = None
    admin_password: str | None = None

    # Sesión por cookie (D24, ADR 0027). Los valores por defecto nunca son inseguros: `Secure`
    # solo se apaga de forma explícita en desarrollo (HTTP sin TLS).
    session_days: int = Field(default=30, ge=1)
    session_cookie_secure: bool = True
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_cookie_domain: str | None = None

    # CSRF por `Origin` (D24): orígenes extra aceptados en métodos no seguros, separados por
    # comas. Vacío = solo el mismo origen del despliegue (D4).
    allowed_origins: list[str] = []

    # Política de contraseña (D24). El mínimo actual se conserva como suelo para no invalidar
    # cuentas existentes; en producción conviene subirlo.
    password_min_length: int = Field(default=8, ge=8)

    # Límite de peticiones (D23, ADR 0026). `0` desactiva el límite de ese alcance.
    rate_limit_enabled: bool = True
    rate_limit_auth_attempts: int = Field(default=10, ge=0)
    rate_limit_auth_window_seconds: int = Field(default=300, ge=1)
    rate_limit_chat_attempts: int = Field(default=30, ge=0)
    rate_limit_chat_window_seconds: int = Field(default=60, ge=1)

    # Avatares: volumen local fuera de los estáticos (ADR 0017).
    avatar_storage_dir: str = "var/avatars"

    # Build de la SPA que sirve FastAPI en el mismo origen (D4). Si está vacío, se usa
    # `frontend/build` del repo; si el directorio no existe, no se monta (modo desarrollo).
    frontend_dist_dir: str | None = None

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_allowed_origins(cls, value: object) -> object:
        """Acepta `a,b` desde el entorno además de la lista JSON que espera pydantic-settings."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _forbid_debug_in_production(self) -> "Settings":
        if self.environment == "production" and self.debug:
            raise ValueError("debug no puede estar activo en producción")
        return self


@lru_cache
def get_settings() -> Settings:
    """Instancia única de la configuración."""
    return Settings()
