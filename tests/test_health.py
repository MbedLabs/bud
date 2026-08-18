"""Liveness vs readiness probe behaviour.

Guards the release blocker: ``/api/health`` must never claim a database
connection it has not verified, and ``/api/ready`` must actually check the
database.
"""


def test_health_is_liveness_only_and_does_not_claim_db(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    # The bug this fixes: liveness previously hard-coded database="connected".
    assert body.get("database") != "connected"


def test_ready_probe_reports_database_connected(client):
    resp = client.get("/api/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["database"] == "connected"
