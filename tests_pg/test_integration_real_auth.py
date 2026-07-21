"""End-to-end integration flow against real PostgreSQL with real authentication.

No dependency overrides: this exercises the exact login -> JWT -> DB-backed
mutation path a real client uses, over the alembic-built schema. It is the layer
the audit flagged as missing (the SQLite suite bypasses both Postgres and auth).
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    "postgres" not in os.environ.get("DATABASE_URL", ""),
    reason="requires a PostgreSQL DATABASE_URL (CI-only)",
)

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "ci-admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ci-admin-password-123")


def _login(client) -> str:
    resp = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_ready_probe_hits_real_database(client):
    resp = client.get("/api/ready")
    assert resp.status_code == 200
    assert resp.json()["database"] == "connected"


def test_wrong_password_is_rejected(client):
    resp = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": "definitely-the-wrong-password"},
    )
    assert resp.status_code == 401


def test_unauthenticated_write_is_rejected(client):
    # Real auth (not an override): the create endpoint must reject a missing JWT.
    resp = client.post("/api/products", json={"name": "should-not-persist"})
    assert resp.status_code == 401


def test_real_login_then_db_backed_write_and_read(client):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/products",
        json={"name": "Integration Widget", "description": "created via real JWT"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]

    # Round-trips through PostgreSQL: the row is really there on a fresh read.
    listed = client.get("/api/products", headers=headers)
    assert listed.status_code == 200
    assert any(p["id"] == product_id for p in listed.json())
