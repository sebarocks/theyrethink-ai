"""Registro de métricas del proceso en formato Prometheus (D25, ADR `0028`).

Es deliberadamente mínimo: cinco contadores y dos indicadores, sin dependencias. El registro es
**por proceso** (con `WEB_CONCURRENCY > 1` hay uno por worker), así que Prometheus debe sumar por
instancia; el endpoint `/metrics` no agrega entre workers.

La métrica que justifica esto es la de D7: `memory_injected_tokens_last` frente a
`memory_injection_budget_tokens`, que decide con datos si la compactación de memoria (Fase 7)
hace falta.
"""

from __future__ import annotations

import threading

__all__ = ["increment", "render", "reset", "set_value"]

# nombre -> (tipo, ayuda)
_METRICS: dict[str, tuple[str, str]] = {
    "chat_turns_total": ("counter", "Turnos de chat completados."),
    "memory_injected_tokens_total": ("counter", "Tokens de memoria inyectados (acumulado)."),
    "memory_injected_tokens_last": ("gauge", "Tokens de memoria inyectados en el ultimo turno."),
    "memory_injection_budget_tokens": ("gauge", "Techo de inyeccion vigente (0.4 x contexto)."),
    "memory_facts_injected_total": ("counter", "Hechos de memoria inyectados (acumulado)."),
    "prompt_cache_read_tokens_total": (
        "counter",
        "Tokens de prompt servidos desde cache del proveedor (best-effort).",
    ),
}

_values: dict[str, float] = {name: 0.0 for name in _METRICS}
_lock = threading.Lock()


def increment(name: str, amount: float = 1.0) -> None:
    """Suma `amount` al contador o indicador indicado."""
    with _lock:
        _values[name] = _values.get(name, 0.0) + amount


def set_value(name: str, value: float) -> None:
    """Fija el valor de un indicador (o contador, aunque no es lo habitual)."""
    with _lock:
        _values[name] = value


def reset() -> None:
    """Vuelve todos los valores a cero. Lo usan los tests."""
    with _lock:
        for name in _values:
            _values[name] = 0.0


def render() -> str:
    """Devuelve el registro en formato de texto de Prometheus."""
    lines: list[str] = []
    with _lock:
        snapshot = dict(_values)
    for name, (kind, help_text) in _METRICS.items():
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {kind}")
        lines.append(f"{name} {snapshot[name]:g}")
    return "\n".join(lines) + "\n"
