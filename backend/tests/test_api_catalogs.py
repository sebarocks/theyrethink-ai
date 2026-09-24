"""Contrato de autorización y rutas de los catálogos administrativos."""

from app.api.v1.catalogs import router


def test_catalog_routes_include_reads_mutations_and_associations() -> None:
    routes = {(route.path, frozenset(route.methods or ())) for route in router.routes}
    assert ("/roles", frozenset({"GET"})) in routes
    assert ("/roles", frozenset({"POST"})) in routes
    assert ("/roles/{role_id}", frozenset({"PATCH"})) in routes
    assert ("/roles/{role_id}", frozenset({"DELETE"})) in routes
    assert ("/sources", frozenset({"GET"})) in routes
    assert ("/sources", frozenset({"POST"})) in routes
    assert ("/agents/{agent_id}/sources", frozenset({"GET"})) in routes
    assert ("/agents/{agent_id}/sources/{source_id}", frozenset({"PUT"})) in routes
    assert ("/agents/{agent_id}/sources/{source_id}", frozenset({"DELETE"})) in routes
