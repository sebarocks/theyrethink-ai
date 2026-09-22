"""Contrato y validadores básicos de avatares."""

from app.api.v1.agents import _AVATAR_TYPES, MAX_AVATAR_BYTES, router


def test_avatar_routes_are_explicit() -> None:
    routes = {(route.path, frozenset(route.methods or ())) for route in router.routes}
    assert ("/agents/{agent_id}/avatar", frozenset({"POST"})) in routes
    assert ("/agents/{agent_id}/avatar", frozenset({"GET"})) in routes
    assert ("/agents/{agent_id}/avatar", frozenset({"DELETE"})) in routes


def test_avatars_allow_only_non_svg_raster_signatures() -> None:
    assert MAX_AVATAR_BYTES == 5 * 1024 * 1024
    assert set(_AVATAR_TYPES) == {"image/jpeg", "image/png", "image/gif", "image/webp"}
    assert not any(extension == ".svg" for _, extension in _AVATAR_TYPES.values())
