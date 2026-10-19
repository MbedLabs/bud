"""One-time tokens must never appear in application/access logs."""

import logging


def test_one_time_tokens_never_reach_access_logs(unauthenticated_client, caplog):
    """A token sent in the body, and a token sent in the query string, never appear in the
    application's own log records, which do record the request.
    """
    secret = "SUPERSECRET-DO-NOT-LOG-0123456789abcdef"

    with caplog.at_level(logging.INFO):
        unauthenticated_client.post("/api/auth/invite-info", json={"token": secret})
        unauthenticated_client.post(f"/api/auth/invite-info?token={secret}", json={"token": secret})

    app_logs = "\n".join(
        r.getMessage() for r in caplog.records if r.name.startswith(("bud", "app"))
    )
    assert "/api/auth/invite-info" in app_logs
    assert secret not in app_logs
