"""Hashing de contrasenas con Argon2 (AGENTS.md §5).

`argon2-cffi` trae parametros por defecto razonables (RFC 9106); no se fijan a mano salvo
necesidad medida, para no congelar coste de CPU sin justificacion.

Incluye la verificacion de los hashes **heredados** de Werkzeug (`scrypt:N:r:p$salt$hex`) que
deja la migracion de la Fase 5. Se resuelve con `hashlib.scrypt` de la stdlib en vez de
`werkzeug.security` para no arrastrar una dependencia de runtime; el formato es estable y
esta documentado (ver ADR `0023`). El re-hash a Argon2 ocurre en el primer login exitoso.
"""

from __future__ import annotations

import hashlib
import hmac

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

__all__ = ["hash_password", "verify_password", "needs_rehash"]

_hasher = PasswordHasher()
_LEGACY_SCRYPT_PREFIX = "scrypt:"


def _verify_legacy_scrypt(password_hash: str, password: str) -> bool:
    """Verifica un hash `scrypt:N:r:p$salt$hex` generado por Werkzeug."""
    try:
        method, salt, expected = password_hash.split("$", 2)
        _, raw_n, raw_r, raw_p = method.split(":")
        n, r, p = int(raw_n), int(raw_r), int(raw_p)
    except ValueError:
        return False
    try:
        derived = hashlib.scrypt(
            password.encode(),
            salt=salt.encode(),
            n=n,
            r=r,
            p=p,
            maxmem=132 * n * r * p,
        ).hex()
    except (ValueError, MemoryError):
        return False
    return hmac.compare_digest(derived, expected)


def hash_password(password: str) -> str:
    """Devuelve el hash Argon2 de una contrasena en claro."""
    if not password:
        raise ValueError("La contraseña no puede estar vacía")
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Comprueba una contrasena contra su hash (Argon2 o `scrypt` heredado)."""
    if password_hash.startswith(_LEGACY_SCRYPT_PREFIX):
        return _verify_legacy_scrypt(password_hash, password)
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True si el hash debe reescribirse (parametros obsoletos o `scrypt` heredado)."""
    if password_hash.startswith(_LEGACY_SCRYPT_PREFIX):
        return True
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True
