"""Tests for the domain exception -> HTTP response translation."""

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.api.error_handlers import register_exception_handlers
from app.core.exceptions import EntityNotFoundError


def _build_app_with_failing_routes() -> FastAPI:
    """A minimal app with routes that always raise, for testing error handling in isolation."""
    app = FastAPI()
    register_exception_handlers(app)

    router = APIRouter()

    @router.get("/boom")
    async def boom() -> None:
        raise EntityNotFoundError("Agent", "abc-123")

    @router.get("/crash")
    async def crash() -> None:
        raise RuntimeError("unexpected failure with sensitive internals")

    app.include_router(router)
    return app


def test_domain_error_returns_structured_404() -> None:
    client = TestClient(_build_app_with_failing_routes(), raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "entity_not_found"
    assert "Agent" in body["message"]


def test_unhandled_exception_does_not_leak_internals() -> None:
    client = TestClient(_build_app_with_failing_routes(), raise_server_exceptions=False)

    response = client.get("/crash")

    assert response.status_code == 500
    body = response.json()
    assert body["error_code"] == "internal_error"
    assert "sensitive internals" not in body["message"]


def test_unmatched_route_returns_structured_error(client: TestClient) -> None:
    """Even Starlette's built-in 404 for unmatched routes should use the project's ErrorResponse shape."""
    response = client.get("/api/v1/definitely-not-a-real-route")

    assert response.status_code == 404
    assert response.json()["error_code"] == "http_error"