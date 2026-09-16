"""Liveness vs readiness probe behaviour."""


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
