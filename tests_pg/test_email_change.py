"""Verified email-change flow and invitation-as-verification (real PostgreSQL)."""

import asyncio
import os
import re

import asyncpg
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


def _replace_pending_email_directly(user_id: int, pending_email: str) -> None:
    """Recreate the stale-approval race outcome without timing-dependent sleeps."""

    async def update_pending_email() -> None:
        database_url = os.environ["DATABASE_URL"].replace(
            "postgresql+asyncpg://", "postgresql://", 1
        )
        connection = await asyncpg.connect(database_url)
        try:
            await connection.execute(
                "UPDATE users SET pending_email = $1 WHERE id = $2",
                pending_email,
                user_id,
            )
        finally:
            await connection.close()

    asyncio.run(update_pending_email())


def test_email_change_requires_confirmation_and_ends_sessions(client):
    admin_access = _admin_access(client)
    old_email = "mover-old@example.com"
    new_email = "mover-new@example.com"
    password = "Mover-Password-123"
    _create_user(client, admin_access, old_email, password)

    login1 = _login(client, old_email, password)
    assert login1.status_code == 200, login1.text
    access1 = login1.json()["access_token"]
    refresh1 = client.cookies.get(COOKIE)

    # The account holder can only request the change. No email is sent before an
    # administrator approves it.
    captured: dict[str, str] = {}
    import app.api.users as users_module

    original = users_module.send_email_change_email
    users_module.send_email_change_email = lambda **kw: captured.update(
        link=kw["confirm_link"],
        old_email=kw["old_email"],
        new_email=kw["new_email"],
    )
    try:
        req = client.post(
            "/api/auth/me/email",
            json={"current_password": password, "new_email": new_email},
            headers=_bearer(access1),
        )
        assert req.status_code == 200, req.text
        assert captured == {}

        pending = client.get("/api/auth/me", headers=_bearer(access1))
        assert pending.json()["email_change_status"] == "requested"

        approve = client.post(
            f"/api/users/{pending.json()['id']}/email/approve",
            headers=_bearer(admin_access),
        )
        assert approve.status_code == 200, approve.text
    finally:
        users_module.send_email_change_email = original

    # Approved but unconfirmed: login email is unchanged and the confirmation
    # email names both addresses.
    me = client.get("/api/auth/me", headers=_bearer(access1))
    assert me.status_code == 200
    assert me.json()["email"] == old_email
    assert me.json()["pending_email"] == new_email
    assert me.json()["email_change_status"] == "awaiting_confirmation"
    assert captured["old_email"] == old_email
    assert captured["new_email"] == new_email
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
    assert me2.json()["email_change_status"] is None
    assert me2.json()["email_verified_at"] is not None


def test_confirmation_token_cannot_apply_a_different_pending_email(client):
    import app.api.users as users_module

    admin_access = _admin_access(client)
    old_email = "race-old@example.com"
    approved_email = "race-approved@example.com"
    unapproved_email = "race-unapproved@example.com"
    password = "Race-Password-123"
    _create_user(client, admin_access, old_email, password)

    login = _login(client, old_email, password)
    user_access = login.json()["access_token"]
    pending = client.post(
        "/api/auth/me/email",
        json={"current_password": password, "new_email": approved_email},
        headers=_bearer(user_access),
    )
    assert pending.status_code == 200, pending.text
    user_id = client.get("/api/auth/me", headers=_bearer(user_access)).json()["id"]

    captured: dict[str, str] = {}
    original = users_module.send_email_change_email
    users_module.send_email_change_email = lambda **kw: captured.update(link=kw["confirm_link"])
    try:
        approved = client.post(
            f"/api/users/{user_id}/email/approve",
            headers=_bearer(admin_access),
        )
        assert approved.status_code == 200, approved.text
    finally:
        users_module.send_email_change_email = original

    token = re.search(r"token=([^&\s]+)", captured["link"]).group(1)
    _replace_pending_email_directly(user_id, unapproved_email)

    confirmed = client.post("/api/auth/confirm-email-change", json={"token": token})
    assert confirmed.status_code == 400, confirmed.text
    assert _login(client, old_email, password).status_code == 200
    assert _login(client, approved_email, password).status_code == 401
    assert _login(client, unapproved_email, password).status_code == 401


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


def test_admin_email_change_uses_confirmation_and_generic_update_cannot_bypass(client):
    import app.api.users as users_module

    admin_access = _admin_access(client)
    old_email = "admin-flow-old@example.com"
    new_email = "admin-flow-new@example.com"
    password = "Admin-Flow-Password-123"
    _create_user(client, admin_access, old_email, password)
    user = next(
        item
        for item in client.get("/api/users", headers=_bearer(admin_access)).json()
        if item["email"] == old_email
    )

    bypass = client.patch(
        f"/api/users/{user['id']}",
        json={"email": new_email},
        headers=_bearer(admin_access),
    )
    assert bypass.status_code == 422

    captured: dict[str, str] = {}
    original = users_module.send_email_change_email
    users_module.send_email_change_email = lambda **kw: captured.update(link=kw["confirm_link"])
    try:
        started = client.post(
            f"/api/users/{user['id']}/email",
            json={"new_email": new_email},
            headers=_bearer(admin_access),
        )
        assert started.status_code == 200, started.text
        assert started.json()["email"] == old_email
        assert started.json()["email_change_status"] == "awaiting_confirmation"
    finally:
        users_module.send_email_change_email = original

    token = re.search(r"token=([^&\s]+)", captured["link"]).group(1)
    confirmed = client.post("/api/auth/confirm-email-change", json={"token": token})
    assert confirmed.status_code == 200, confirmed.text
    assert _login(client, old_email, password).status_code == 401
    assert _login(client, new_email, password).status_code == 200


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
