"""Password change / reset invalidates all existing sessions (real PostgreSQL).

Each test provisions its own throwaway user via the admin API so it never
disturbs the admin account the session-scoped client logs in as. Proves the
audit's guarantees: access tokens and refresh tokens minted before the
credential change stop working, the old password can no longer log in, and the
new one can.
"""

import os
import re

import pytest

from tests_pg.conftest import unique_email

pytestmark = pytest.mark.skipif(
    "postgres" not in os.environ.get("DATABASE_URL", ""),
    reason="requires a PostgreSQL DATABASE_URL (CI-only)",
)

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "ci-admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ci-admin-password-123")
COOKIE = "bud_refresh_token"


def _bearer(access: str) -> dict:
    return {"Authorization": f"Bearer {access}"}


def _admin_access(client) -> str:
    client.cookies.clear()
    resp = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _create_user(client, admin_access: str, email: str, password: str) -> None:
    resp = client.post(
        "/api/users",
        json={"email": email, "full_name": "Victim", "password": password, "role": "viewer"},
        headers=_bearer(admin_access),
    )
    assert resp.status_code == 201, resp.text


def _login(client, email: str, password: str):
    client.cookies.clear()
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_password_change_invalidates_all_sessions(client):
    admin_access = _admin_access(client)
    email = unique_email("pwchange-victim")
    old_pw = "OldChange-Password-123"
    new_pw = "NewChange-Password-456"
    _create_user(client, admin_access, email, old_pw)

    login1 = _login(client, email, old_pw)
    assert login1.status_code == 200, login1.text
    access1 = login1.json()["access_token"]
    refresh1 = client.cookies.get(COOKIE)
    assert client.get("/api/auth/me", headers=_bearer(access1)).status_code == 200

    change = client.put(
        "/api/auth/me/password",
        json={"current_password": old_pw, "new_password": new_pw},
        headers=_bearer(access1),
    )
    assert change.status_code == 200, change.text

    # Pre-change access token is now rejected (session_version bumped).
    assert client.get("/api/auth/me", headers=_bearer(access1)).status_code == 401
    # Pre-change refresh token is revoked.
    client.cookies.clear()
    assert client.post("/api/auth/refresh", cookies={COOKIE: refresh1}).status_code == 401
    # Old password no longer works; the new one does.
    assert _login(client, email, old_pw).status_code == 401
    assert _login(client, email, new_pw).status_code == 200


def test_password_reset_invalidates_all_sessions(client):
    import app.api.auth as auth_module

    admin_access = _admin_access(client)
    email = unique_email("pwreset-victim")
    old_pw = "OldReset-Password-123"
    new_pw = "NewReset-Password-456"
    _create_user(client, admin_access, email, old_pw)

    login1 = _login(client, email, old_pw)
    assert login1.status_code == 200, login1.text
    access1 = login1.json()["access_token"]
    refresh1 = client.cookies.get(COOKIE)
    assert client.get("/api/auth/me", headers=_bearer(access1)).status_code == 200

    # Capture the one-time reset token from the email the endpoint would send.
    captured: dict[str, str] = {}
    original = auth_module.send_password_reset_email

    def _capture(*, to_email, full_name, reset_link):
        captured["link"] = reset_link

    auth_module.send_password_reset_email = _capture
    try:
        fp = client.post("/api/auth/forgot-password", json={"email": email})
        assert fp.status_code == 200, fp.text
    finally:
        auth_module.send_password_reset_email = original

    match = re.search(r"token=([^&\s]+)", captured.get("link", ""))
    assert match, f"no reset token in link: {captured!r}"
    token = match.group(1)

    reset = client.post("/api/auth/reset-password", json={"token": token, "new_password": new_pw})
    assert reset.status_code == 200, reset.text

    # Pre-reset access token rejected, pre-reset refresh revoked.
    assert client.get("/api/auth/me", headers=_bearer(access1)).status_code == 401
    client.cookies.clear()
    assert client.post("/api/auth/refresh", cookies={COOKIE: refresh1}).status_code == 401
    # Old password rejected; new password works.
    assert _login(client, email, old_pw).status_code == 401
    assert _login(client, email, new_pw).status_code == 200
