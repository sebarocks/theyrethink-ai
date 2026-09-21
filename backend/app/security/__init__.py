"""Seguridad: hashing de contrasenas (Argon2). La sesion/cookies llegan en la Fase 3."""

from app.security.passwords import hash_password, needs_rehash, verify_password

__all__ = ["hash_password", "needs_rehash", "verify_password"]
