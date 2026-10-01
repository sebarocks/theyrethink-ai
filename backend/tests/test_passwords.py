"""Verificacion de contrasenas: Argon2 y hashes heredados de Werkzeug (Fase 5).

El formato heredado es `scrypt:N:r:p$salt$hex` (Werkzeug). Se verifica con la stdlib, sin
`werkzeug` en runtime (ADR `0023`).
"""

import hashlib

from app.security import hash_password, needs_rehash, verify_password


def _werkzeug_scrypt(password: str, *, n: int = 2**15, r: int = 8, p: int = 1) -> str:
    """Genera un hash con el mismo formato que `werkzeug.security.generate_password_hash`."""
    salt = "0123456789abcdef"
    derived = hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=n, r=r, p=p, maxmem=132 * n * r * p
    ).hex()
    return f"scrypt:{n}:{r}:{p}${salt}${derived}"


def test_argon2_roundtrip() -> None:
    hashed = hash_password("secreta123")
    assert hashed.startswith("$argon2")
    assert verify_password(hashed, "secreta123")
    assert not verify_password(hashed, "otra")
    assert not needs_rehash(hashed)


def test_legacy_werkzeug_scrypt_is_verified_and_flagged_for_rehash() -> None:
    hashed = _werkzeug_scrypt("secreta123")
    assert verify_password(hashed, "secreta123")
    assert not verify_password(hashed, "otra")
    assert needs_rehash(hashed)


def test_malformed_hashes_do_not_raise() -> None:
    for bad in ("", "no-es-un-hash", "scrypt:x:y:z$salt$hash", "scrypt:1:2:3$soloSalt"):
        assert verify_password(bad, "x") is False
