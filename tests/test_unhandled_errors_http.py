"""An unhandled error must still tell the user something they can report."""

from __future__ import annotations

import asyncpg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

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


@pytest.fixture
def conflicting_route():
    """A route that loses the race between checking for a row and writing it."""

    path = "/api/__conflict__"

    @app.get(path)
    async def _conflict():
        raise IntegrityError(
            "INSERT INTO runners ...",
            {},
            asyncpg.exceptions.UniqueViolationError("duplicate key value: runners_account_key"),
        )

    yield path
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != path]


@pytest.fixture
def missing_reference_route():
    path = "/api/__fk__"

    @app.get(path)
    async def _fk():
        raise IntegrityError(
            "DELETE FROM runners ...",
            {},
            asyncpg.exceptions.ForeignKeyViolationError("still referenced"),
        )

    yield path
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != path]


def test_a_lost_race_is_a_conflict_rather_than_a_crash(conflicting_route):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(conflicting_route)

    assert response.status_code == 409
    body = response.json()
    assert body["request_id"] == response.headers["x-request-id"]
    assert body["request_id"] in body["detail"]
    assert "already exists" in body["detail"]


def test_a_conflict_does_not_leak_the_constraint(conflicting_route):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(conflicting_route)

    assert "runners_account_key" not in response.text
    assert "INSERT INTO" not in response.text
    assert "UniqueViolationError" not in response.text


def test_a_missing_reference_is_also_a_conflict(missing_reference_route):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(missing_reference_route)

    assert response.status_code == 409
    assert "still referenced" not in response.text
