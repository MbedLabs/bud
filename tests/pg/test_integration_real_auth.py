"""End-to-end integration flow against real PostgreSQL with real authentication."""

import os

import pytest

from tests.pg.conftest import unique_name

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
        json={"name": unique_name("Integration Widget"), "description": "created via real JWT"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]

    # Round-trips through PostgreSQL: the row is really there on a fresh read.
    listed = client.get("/api/products", headers=headers)
    assert listed.status_code == 200
    assert any(p["id"] == product_id for p in listed.json())


def test_a_test_case_whose_results_are_all_skipped_counts_as_skipped(client):
    headers = {"Authorization": f"Bearer {_login(client)}"}
    results = [
        {"test_class": "Suite.Boots", "test_method": "Boots", "passed": True, "duration_seconds": 1},
        {
            "test_class": "Suite.Flashes",
            "test_method": "Flashes",
            "passed": True,
            "duration_seconds": 0,
            "metadata": {"skipped": True},
        },
        {"test_class": "Suite.Fails", "test_method": "Fails", "passed": False, "duration_seconds": 1},
    ]
    uploaded = client.post(
        "/api/results",
        json={"test_suite_name": unique_name("Robot"), "results": results},
        headers=headers,
    )
    assert uploaded.status_code in (200, 201), uploaded.text
    run = client.get(f"/api/test-runs/{uploaded.json()['test_run_id']}", headers=headers).json()
    assert (run["total_tests"], run["passed_tests"], run["failed_tests"], run["skipped_tests"]) == (3, 1, 1, 1)
