"""An unhandled error must still tell the user something they can report."""

from __future__ import annotations

import asyncpg
import pytest
from fastapi import Depends
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.db import database
from app.db.database import get_db
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


@pytest.fixture
def late_conflict_route(monkeypatch):
    """A route whose session commit fails after the endpoint has returned."""

    class _FailingCommitSession:
        """A session that refuses its commit with a unique violation."""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def commit(self):
            raise IntegrityError(
                "INSERT INTO runners ...",
                {},
                asyncpg.exceptions.UniqueViolationError("duplicate key value: runners_account_key"),
            )

        async def rollback(self):
            return None

        async def close(self):
            return None

    monkeypatch.setattr(database, "async_session_maker", _FailingCommitSession)
    path = "/api/__late_conflict__"

    @app.get(path)
    async def _late_conflict(db=Depends(get_db, scope="function")):
        return {"ok": True}

    yield path
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != path]


def test_a_failing_commit_is_answered_as_a_conflict(late_conflict_route):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(late_conflict_route)

    assert response.status_code == 409
    body = response.json()
    assert body["request_id"] == response.headers["x-request-id"]
    assert "runners_account_key" not in response.text


def _session_dependencies(dependant):
    """Yield every dependency on get_db below a route's dependant."""
    for sub in dependant.dependencies:
        if sub.call is get_db:
            yield sub
        yield from _session_dependencies(sub)


def _api_routes(routes):
    """Yield every API route, including those of included routers."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from _api_routes(included.routes)


def test_every_route_commits_before_its_response():
    routes = list(_api_routes(app.routes))
    late = sorted(
        {
            f"{sorted(r.methods)} {r.path}"
            for r in routes
            for dep in _session_dependencies(r.dependant)
            if dep.scope != "function"
        }
    )

    assert any(True for r in routes for _ in _session_dependencies(r.dependant))
    assert late == []
