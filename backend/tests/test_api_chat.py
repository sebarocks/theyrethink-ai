"""Contrato del endpoint SSE de chat."""

from app.api.v1.chat import HEARTBEAT_SECONDS, _event, router


def test_chat_route_is_post_message_stream() -> None:
    routes = {(route.path, frozenset(route.methods or ())) for route in router.routes}
    assert ("/threads/{thread_id}/messages", frozenset({"POST"})) in routes
    assert HEARTBEAT_SECONDS > 0


def test_chat_route_includes_message_history() -> None:
    routes = {(route.path, frozenset(route.methods or ())) for route in router.routes}
    assert ("/threads/{thread_id}/messages", frozenset({"GET"})) in routes


def test_sse_event_format_is_stable() -> None:
    assert _event("heartbeat", {}) == "event: heartbeat\ndata: {}\n\n"
    assert _event("chunk", {"text": "hola"}) == ('event: chunk\ndata: {"text": "hola"}\n\n')
