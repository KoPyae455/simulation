"""Shared pytest fixtures for the Simulaca Brain test suite."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A TestClient backed by a fresh app instance per test."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client