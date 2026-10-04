"""Política de contraseñas (D24, ADR `0027`).

Comprueba longitud e identidad, no composición: la evidencia favorece la longitud. Los
parámetros de Argon2 son deliberadamente los de `argon2-cffi` (RFC 9106) y `needs_rehash`
permite subirlos cuando se decida medirlos.
"""

from __future__ import annotations

from app.config import get_settings

__all__ = ["MAX_PASSWORD_LENGTH", "password_policy_error"]

# Coincide con `Field(max_length=128)` de los esquemas de auth.
MAX_PASSWORD_LENGTH = 128


def password_policy_error(
    password: str,
    *,
    username: str | None = None,
    email: str | None = None,
    min_length: int | None = None,
) -> str | None:
    """Motivo del rechazo, o `None` si la contraseña cumple la política.

    Es una función pura (salvo el mínimo por defecto, que sale de la configuración) para poder
    testearla sin base de datos ni petición HTTP.
    """
    minimum = min_length if min_length is not None else get_settings().password_min_length
    if len(password) < minimum:
        return f"La contraseña debe tener al menos {minimum} caracteres."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"La contraseña no puede superar {MAX_PASSWORD_LENGTH} caracteres."

    candidate = password.strip().lower()
    if username and candidate == username.strip().lower():
        return "La contraseña no puede coincidir con el nombre de usuario."
    if email and "@" in email and candidate == email.split("@", 1)[0].strip().lower():
        return "La contraseña no puede coincidir con la parte local del correo."
    return None
