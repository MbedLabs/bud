"""One-time tokens must never appear in application/access logs."""

import logging


def test_one_time_tokens_never_reach_access_logs(unauthenticated_client, caplog):
    secret = "SUPERSECRET-DO-NOT-LOG-0123456789abcdef"

    with caplog.at_level(logging.INFO):
        # Token in the POST body (the new invite-info contract) ...
        unauthenticated_client.post("/api/auth/invite-info", json={"token": secret})
        # ... and, defensively, a legacy token in the query string.
        unauthenticated_client.post(f"/api/auth/invite-info?token={secret}", json={"token": secret})

    # Inspect only the application's own log records (the httpx test client logs
    # its outbound URL, which is a test-harness artifact, not production logging).
    app_logs = "\n".join(
        r.getMessage() for r in caplog.records if r.name.startswith(("bud", "app"))
    )
    # The request was access-logged (so this assertion isn't vacuous) ...
    assert "/api/auth/invite-info" in app_logs
    # ... but the raw token never was, from either the body or the query string.
    assert secret not in app_logs
