"""A constraint violation is answered as a conflict, against a real database."""

from __future__ import annotations

import uuid

import pytest
from fastapi import Depends

from app.db.database import get_db
from app.main import app
from app.models import Runner


@pytest.fixture
def route_conflicting_on_flush():
    """The shape every create endpoint here has: the row is flushed inside the
    endpoint, so the violation surfaces while a response can still be chosen."""

    path = "/api/__flush_conflict__"

    @app.post(path)
    async def _flush_conflict(db=Depends(get_db)):
        account = f"bench-{uuid.uuid4().hex[:8]}"
        db.add(Runner(account=account, password_hash="x", token="t", socket_port=53035))
        db.add(Runner(account=account, password_hash="y", token="u", socket_port=53035))
        await db.flush()
        return {"ok": True}

    yield path
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != path]


def test_a_real_constraint_violation_is_answered_as_a_conflict(client, route_conflicting_on_flush):
    response = client.post(route_conflicting_on_flush)

    assert response.status_code == 409, response.text
    body = response.json()
    assert "already exists" in body["detail"]
    assert body["request_id"]
    assert body["request_id"] in body["detail"]


def test_a_real_conflict_does_not_leak_the_constraint(client, route_conflicting_on_flush):
    response = client.post(route_conflicting_on_flush)

    assert "runners_account_key" not in response.text
    assert "INSERT INTO" not in response.text
    assert "UniqueViolationError" not in response.text
