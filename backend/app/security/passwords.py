"""Hashing de contrasenas con Argon2 (AGENTS.md §5).

`argon2-cffi` trae parametros por defecto razonables (RFC 9106); no se fijan a mano salvo
necesidad medida, para no congelar coste de CPU sin justificacion.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

__all__ = ["hash_password", "verify_password", "needs_rehash"]

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Devuelve el hash Argon2 de una contrasena en claro."""
    if not password:
        raise ValueError("La contraseña no puede estar vacía")
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Comprueba una contrasena contra su hash. Devuelve `False` ante hash invalido."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True si el hash usa parametros obsoletos (p. ej. un hash de Werkzeug migrado)."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True
