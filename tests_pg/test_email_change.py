"""Verified email-change flow and invitation-as-verification (real PostgreSQL)."""

import os
import re

import pytest

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


def _create_user(client, admin_access, email, password, role="viewer"):
    resp = client.post(
        "/api/users",
        json={"email": email, "full_name": "Mover", "password": password, "role": role},
        headers=_bearer(admin_access),
    )
    assert resp.status_code == 201, resp.text


def _login(client, email, password):
    client.cookies.clear()
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_email_change_requires_confirmation_and_ends_sessions(client):
    import app.api.auth as auth_module

    admin_access = _admin_access(client)
    old_email = "mover-old@example.com"
    new_email = "mover-new@example.com"
    password = "Mover-Password-123"
    _create_user(client, admin_access, old_email, password)

    login1 = _login(client, old_email, password)
    assert login1.status_code == 200, login1.text
    access1 = login1.json()["access_token"]
    refresh1 = client.cookies.get(COOKIE)

    # Request the change; capture the confirmation link sent to the NEW address.
    captured: dict[str, str] = {}
    original = auth_module.send_email_change_email
    auth_module.send_email_change_email = lambda **kw: captured.update(link=kw["confirm_link"])
    try:
        req = client.post(
            "/api/auth/me/email",
            json={"current_password": password, "new_email": new_email},
            headers=_bearer(access1),
        )
        assert req.status_code == 200, req.text
    finally:
        auth_module.send_email_change_email = original

    # Unconfirmed: login email is unchanged, and the pending address is recorded.
    me = client.get("/api/auth/me", headers=_bearer(access1))
    assert me.status_code == 200
    assert me.json()["email"] == old_email
    assert me.json()["pending_email"] == new_email
    # The new address cannot log in yet; the old one still can.
    assert _login(client, new_email, password).status_code == 401
    assert _login(client, old_email, password).status_code == 200

    match = re.search(r"token=([^&\s]+)", captured["link"])
    assert match, captured
    confirm = client.post("/api/auth/confirm-email-change", json={"token": match.group(1)})
    assert confirm.status_code == 200, confirm.text

    # Confirmed: pre-change access/refresh tokens are dead, old address cannot log
    # in, new address can, and the account is verified.
    assert client.get("/api/auth/me", headers=_bearer(access1)).status_code == 401
    client.cookies.clear()
    assert client.post("/api/auth/refresh", cookies={COOKIE: refresh1}).status_code == 401
    assert _login(client, old_email, password).status_code == 401
    after = _login(client, new_email, password)
    assert after.status_code == 200, after.text
    me2 = client.get("/api/auth/me", headers=_bearer(after.json()["access_token"]))
    assert me2.json()["email"] == new_email
    assert me2.json()["pending_email"] is None
    assert me2.json()["email_verified_at"] is not None


def test_wrong_current_password_does_not_start_email_change(client):
    admin_access = _admin_access(client)
    email = "mover-guard@example.com"
    password = "Mover-Guard-123"
    _create_user(client, admin_access, email, password)
    login = _login(client, email, password)
    access = login.json()["access_token"]

    resp = client.post(
        "/api/auth/me/email",
        json={"current_password": "wrong-password-xx", "new_email": "guard-new@example.com"},
        headers=_bearer(access),
    )
    assert resp.status_code == 400
    assert client.get("/api/auth/me", headers=_bearer(access)).json()["pending_email"] is None


def test_accepting_invitation_verifies_the_account(client):
    import app.api.users as users_module

    admin_access = _admin_access(client)
    email = "invited-verified@example.com"

    captured: dict[str, str] = {}
    original = users_module.send_invite_email
    users_module.send_invite_email = lambda **kw: captured.update(link=kw["invite_link"])
    try:
        resp = client.post(
            "/api/users/invite",
            json={"email": email, "full_name": "Invited", "role": "viewer"},
            headers=_bearer(admin_access),
        )
        assert resp.status_code == 201, resp.text
    finally:
        users_module.send_invite_email = original

    token = re.search(r"token=([^&\s]+)", captured["link"]).group(1)
    accept = client.post(
        "/api/auth/accept-invite", json={"token": token, "password": "Invited-Password-123"}
    )
    assert accept.status_code == 200, accept.text
    assert accept.json()["requires_email_verification"] is False

    login = _login(client, email, "Invited-Password-123")
    assert login.status_code == 200
    me = client.get("/api/auth/me", headers=_bearer(login.json()["access_token"]))
    assert me.json()["email_verified_at"] is not None
