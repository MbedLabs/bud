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


def _station_headers(client):
    """Enroll a station through the real authentication API."""
    headers = {"Authorization": f"Bearer {_login(client)}"}
    account = unique_name("station").replace(" ", "-")
    key = client.post(
        "/api/runners/api-keys", json={"label": account, "station_name": account}, headers=headers
    )
    assert key.status_code == 201, key.text
    enrolled = client.post(
        "/api/runners/register",
        json={"username": account, "password": "station-password-123", "socket_port": 53035},
        headers={"X-API-Key": key.json()["api_key"]},
    )
    assert enrolled.status_code == 201, enrolled.text
    return {"Authorization": f"Bearer {enrolled.json()['token']}"}


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
    station_headers = _station_headers(client)
    results = [
        {
            "test_class": "Suite.Boots",
            "test_method": "Boots",
            "passed": True,
            "duration_seconds": 1,
        },
        {
            "test_class": "Suite.Flashes",
            "test_method": "Flashes",
            "passed": True,
            "duration_seconds": 0,
            "metadata": {"skipped": True},
        },
        {
            "test_class": "Suite.Fails",
            "test_method": "Fails",
            "passed": False,
            "duration_seconds": 1,
        },
    ]
    uploaded = client.post(
        "/api/results",
        json={"test_suite_name": unique_name("Robot"), "results": results},
        headers=station_headers,
    )
    assert uploaded.status_code in (200, 201), uploaded.text
    run = client.get(f"/api/test-runs/{uploaded.json()['test_run_id']}", headers=headers).json()
    assert (run["total_tests"], run["passed_tests"], run["failed_tests"], run["skipped_tests"]) == (
        3,
        1,
        1,
        1,
    )


def test_human_admin_cannot_report_station_execution(client):
    human = {"Authorization": f"Bearer {_login(client)}"}
    station = _station_headers(client)
    payload = {"test_suite_name": unique_name("Producer"), "test_case_list": "Suite"}
    created = client.post("/api/test-runs", json=payload, headers=station)
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]
    assert client.post("/api/test-runs", json=payload, headers=human).status_code == 403
    assert (
        client.patch(
            f"/api/test-runs/{run_id}", json={"total_tests": 99}, headers=human
        ).status_code
        == 403
    )
    results = {"results": [{"test_class": "Suite", "test_method": "test_one", "passed": True}]}
    assert client.post("/api/results", json=results, headers=human).status_code == 403
    results["test_run_id"] = run_id
    assert client.post("/api/results", json=results, headers=human).status_code == 403
    run = client.get(f"/api/test-runs/{run_id}", headers=human).json()
    assert run["total_tests"] == 0
    assert run["status"] == "Running"
    submitted = client.post("/api/results", json=results, headers=station)
    assert submitted.status_code == 201, submitted.text
