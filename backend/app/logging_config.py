"""Configuración de logging estructurado y correlación por `request_id` (D25, ADR `0028`).

`log_event` no cambia: sigue emitiendo un nombre de evento y campos por `extra`. Lo que cambia
es el formateador (JSON en producción) y que cada registro incluye el `request_id` del contexto.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

from app.config import Settings

__all__ = ["JsonFormatter", "configure_logging", "request_id_var"]

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Atributos estándar de `logging.LogRecord`: todo lo demas se trata como campo del evento.
_RESERVED: frozenset[str] = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Un objeto JSON por línea, con el `request_id` del contexto."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_") or key == "message":
                continue
            payload[key] = value
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(settings: Settings) -> None:
    """Instala un único handler con el formato configurado.

    Incluye los loggers de `uvicorn`: la CLI los configura **antes** de importar la app, así que
    sin esto los logs de acceso quedarían en texto y sin `request_id`, rompiendo el formato
    uniforme que pide D25.
    """
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(settings.log_level.upper())
