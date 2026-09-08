"""An unhandled error must still tell the user something they can report."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def exploding_route():
    path = "/api/__boom__"

    @app.get(path)
    async def _boom():
        raise RuntimeError("something went bang")

    yield path
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != path]


def test_a_500_carries_a_reference_the_user_can_quote(exploding_route):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(exploding_route)

    assert response.status_code == 500
    body = response.json()
    reference = response.headers["x-request-id"]

    assert reference
    assert body["request_id"] == reference
    assert reference in body["detail"]


def test_a_500_does_not_leak_the_exception(exploding_route):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(exploding_route)

    assert "something went bang" not in response.text
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text
