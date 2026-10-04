"""Comprobación de `Origin`/`Referer` para métodos no seguros (D24, ADR `0027`).

`SameSite=Lax` ya impide que el navegador mande la cookie en un POST cross-site; esto añade una
segunda barrera explícita y verificable. Si la cabecera no viene —clientes no navegador, tests,
`curl`— no hay nada que comparar y se acepta.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from starlette.requests import Request

__all__ = ["UNSAFE_METHODS", "origin_rejection_reason"]

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _scheme_and_host(value: str) -> tuple[str, str] | None:
    """Normaliza una URL o un `Origin` a `(esquema, host)`; `None` si no es utilizable."""
    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        return None
    return parts.scheme, parts.netloc


def origin_rejection_reason(request: Request, allowed_origins: list[str]) -> str | None:
    """Motivo por el que se rechaza la petición, o `None` si es aceptable.

    Orden de comprobación: mismo `host` que la petición (incluye el caso del proxy TLS, donde el
    esquema puede diferir pero el host no) y, después, la allowlist de orígenes completos.
    """
    if request.method not in UNSAFE_METHODS:
        return None

    raw = request.headers.get("origin") or request.headers.get("referer")
    if not raw:
        return None

    parsed = _scheme_and_host(raw)
    if parsed is None:
        return "Origen de la petición no válido."
    scheme, origin_host = parsed
    if f"{scheme}://{origin_host}" in allowed_origins or origin_host in allowed_origins:
        return None

    request_host = request.headers.get("host")
    if request_host and origin_host == request_host:
        return None

    return "Origen de la petición no permitido."
