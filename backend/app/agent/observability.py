"""Logging estructurado minimo con ids de correlacion (adelantado de Fase 6, §4 hueco 7).

Depurar un grafo sin logs correlacionados es caro (propuesta §13). Aqui solo se fija el
formato: un evento con nombre y campos, entre ellos `thread_id`, `agent_id` y `user_id`.
"""

from __future__ import annotations

import logging

__all__ = ["get_logger", "log_event"]

_LOGGER_NAME = "app.agent"


def get_logger() -> logging.Logger:
    """Logger del nucleo del agente."""
    return logging.getLogger(_LOGGER_NAME)


def log_event(event: str, *, level: int = logging.INFO, **fields: object) -> None:
    """Emite un evento estructurado: el nombre va en `event` y los ids como campos."""
    get_logger().log(level, event, extra={"event": event, **fields})
