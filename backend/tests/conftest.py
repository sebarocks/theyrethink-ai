"""Configuración compartida de los tests.

Los tests del núcleo no tocan red ni base de datos: usan dobles (ver AGENTS.md §6).
Este módulo solo garantiza que la configuración tenga valores válidos antes de importarla.
"""

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-with-at-least-32-characters")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://theyrethink:theyrethink@localhost:5432/theyrethink",
)
