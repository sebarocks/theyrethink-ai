"""Pruebas unitarias y de contrato del bloque de autenticación."""

from app.api.deps import SESSION_COOKIE, hash_session_token
from app.api.v1.auth import router
from app.security import hash_password, verify_password


def test_passwords_use_argon2_and_verify() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2")
    assert verify_password(hashed, "correct horse battery staple")
    assert not verify_password(hashed, "wrong")


def test_session_token_is_stored_as_fixed_length_digest() -> None:
    digest = hash_session_token("opaque-token")
    assert len(digest) == 64
    assert digest != "opaque-token"


def test_auth_contract_exposes_public_and_protected_operations() -> None:
    routes = {(route.path, tuple(route.methods)) for route in router.routes}
    assert ("/auth/register", ("POST",)) in routes
    assert ("/auth/login", ("POST",)) in routes
    assert ("/auth/logout", ("POST",)) in routes
    assert ("/auth/me", ("GET",)) in routes
    assert SESSION_COOKIE == "theyrethink_session"
