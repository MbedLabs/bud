"""Interactive CLI authorization preserves the approving user's account permissions."""

import base64
import hashlib
import json
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select, text

from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
)
from app.models import AuditEvent, User, UserRole, UserToken, UserTokenPurpose
from app.models.access import AccessGroup, AccessGroupMember, Policy
from app.services.token_service import invalidate_all_refresh_tokens

VERIFIER = "v" * 43
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
)


@pytest.fixture(autouse=True)
def reset_limits(fresh_auth_rate_limits):
    """Give each authorization test an independent rate-limit window."""


@pytest.fixture
async def cli_user(db_session):
    """Persist a viewer who can approve clients with their existing permissions."""
    user = User(
        email="cli-user@example.com",
        full_name="CLI User",
        hashed_password=get_password_hash("Cli-Password-123"),
        role=UserRole.viewer,
        is_active=True,
        session_version=1,
    )
    db_session.add(user)
    group = AccessGroup(
        name="CLI permission test",
        policies=[Policy(name="CLI settings view", permissions={"settings": ["view"]})],
    )
    db_session.add(group)
    await db_session.flush()
    db_session.add(AccessGroupMember(group_id=group.id, user_id=user.id))
    await db_session.commit()
    return user


def bearer(user):
    """Return the existing browser user JWT header."""
    return {
        "Authorization": "Bearer "
        + create_access_token({"sub": str(user.id), "type": "user", "ver": user.session_version})
    }


def start(client, mode="code", **overrides):
    """Start an authorization with a valid S256 challenge."""
    data = {
        "client_name": "Terminal",
        "mode": mode,
        "code_challenge": CHALLENGE,
        "state": "client-state",
    }
    if mode == "callback":
        data["redirect_uri"] = "http://127.0.0.1:41234/callback?client=terminal"
    response = client.post("/api/auth/cli/start", json=data | overrides)
    assert response.status_code == 200, response.text
    return response.json()


def approve(client, user, pending):
    """Approve a pending client using normal user authentication."""
    response = client.post(
        "/api/auth/cli/approve", json={"session_id": pending["session_id"]}, headers=bearer(user)
    )
    assert response.status_code == 200, response.text
    return response.json()


def exchange(client, pending, code, verifier=VERIFIER):
    """Present a one-time code and its original PKCE verifier."""
    return client.post(
        "/api/auth/cli/exchange",
        json={"session_id": pending["session_id"], "code": code, "code_verifier": verifier},
    )


def test_authorization_link_uses_the_ui_path_when_api_base_url_has_a_prefix(
    unauthenticated_client, monkeypatch
):
    monkeypatch.setattr("app.core.config.settings.APP_BASE_URL", "https://bud.example.test/api")
    pending = start(unauthenticated_client)
    assert pending["authorize_url"] == f"/auth/cli?session_id={pending['session_id']}"


@pytest.mark.parametrize("mode", ["callback", "code"])
async def test_cli_authorization_issues_the_approving_user_and_one_audit_event(
    unauthenticated_client, db_session, cli_user, mode
):
    client = unauthenticated_client
    pending = start(client, mode)
    assert pending["expires_at"].endswith("Z")
    assert urlsplit(pending["authorize_url"]).path == "/auth/cli"
    assert parse_qs(urlsplit(pending["authorize_url"]).query) == {
        "session_id": [pending["session_id"]]
    }
    expiry = datetime.fromisoformat(pending["expires_at"].replace("Z", "+00:00")).replace(
        tzinfo=None
    )
    assert timedelta(minutes=9) < expiry - datetime.utcnow() <= timedelta(minutes=10)
    metadata = client.get(
        f"/api/auth/cli/sessions/{pending['session_id']}", headers=bearer(cli_user)
    )
    assert metadata.status_code == 200
    assert metadata.json()["client_name"] == "Terminal"
    assert metadata.json()["consumed"] is False
    assert set(metadata.json()) == {
        "session_id",
        "client_name",
        "mode",
        "redirect_uri",
        "expires_at",
        "consumed",
    }
    approved = approve(client, cli_user, pending)
    if mode == "callback":
        callback = urlsplit(approved["redirect_to"])
        assert (callback.scheme, callback.netloc, callback.path) == (
            "http",
            "127.0.0.1:41234",
            "/callback",
        )
        query = parse_qs(callback.query)
        assert query["state"] == ["client-state"]
        assert query["client"] == ["terminal"]
        code = query["code"][0]
    else:
        code = approved["exchange_code"]
        assert approved["expires_at"] == pending["expires_at"]
    stored = (
        await db_session.execute(
            text("SELECT exchange_code_hash FROM cli_auth_sessions WHERE id = :id"),
            {"id": pending["session_id"].replace("-", "")},
        )
    ).scalar_one()
    assert stored == hashlib.sha256(code.encode()).hexdigest()
    result = exchange(client, pending, code)
    assert result.status_code == 200, result.text
    tokens = result.json()
    assert set(tokens) == {"access_token", "refresh_token", "token_type", "user"}
    assert tokens["token_type"] == "bearer"
    original = client.get("/api/auth/me", headers=bearer(cli_user)).json()
    assert tokens["user"] == original
    assert original["role"] == "viewer"
    assert "settings.view" in original["permissions"]
    assert "settings.edit" not in original["permissions"]
    jwt = decode_access_token(tokens["access_token"])
    assert (jwt["sub"], jwt["type"], jwt["ver"]) == (str(cli_user.id), "user", 1)
    assert isinstance(jwt["cli_refresh_id"], int)
    token_row = await db_session.get(UserToken, jwt["cli_refresh_id"])
    assert token_row.purpose == UserTokenPurpose.refresh
    assert token_row.token_hash == hashlib.sha256(tokens["refresh_token"].encode()).hexdigest()
    assert "set-cookie" not in result.headers
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        ).status_code
        == 200
    )
    assert exchange(client, pending, code).status_code in (400, 401)
    events = list(
        (
            await db_session.execute(
                select(AuditEvent)
                .where(AuditEvent.action == "auth.cli_exchange")
                .order_by(AuditEvent.id)
            )
        ).scalars()
    )
    assert [event.outcome for event in events] == ["success", "failure"]
    assert events[0].actor_user_id == cli_user.id
    assert events[1].details == {"reason": "expired_or_consumed"}
    audit = json.dumps([event.details for event in events])
    for secret in (code, VERIFIER, tokens["access_token"], tokens["refresh_token"]):
        assert secret not in audit


async def test_cli_refresh_rotates_tokens_and_retires_the_previous_access_jwt(
    unauthenticated_client, cli_user
):
    client = unauthenticated_client
    pending = start(client)
    code = approve(client, cli_user, pending)["exchange_code"]
    tokens = exchange(client, pending, code).json()
    rotated = client.post("/api/auth/cli/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert rotated.status_code == 200, rotated.text
    replacement = rotated.json()
    assert replacement["refresh_token"] != tokens["refresh_token"]
    assert replacement["access_token"] != tokens["access_token"]
    assert replacement["user"] == tokens["user"]
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {replacement['access_token']}"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/cli/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    assert "set-cookie" not in rotated.headers


async def test_revoke_all_refresh_tokens_immediately_rejects_cli_access(
    unauthenticated_client, db_session, cli_user
):
    client = unauthenticated_client
    pending = start(client)
    tokens = exchange(client, pending, approve(client, cli_user, pending)["exchange_code"]).json()
    await invalidate_all_refresh_tokens(db_session, cli_user.id)
    await db_session.commit()
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/cli/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    assert client.get("/api/auth/me", headers=bearer(cli_user)).status_code == 200


async def test_browser_cookie_refresh_is_preserved(unauthenticated_client, cli_user):
    client = unauthenticated_client
    login = client.post(
        "/api/auth/login", json={"email": cli_user.email, "password": "Cli-Password-123"}
    )
    assert login.status_code == 200
    assert "cli_refresh_id" not in decode_access_token(login.json()["access_token"])
    assert client.cookies.get("bud_refresh_token")
    response = client.post("/api/auth/refresh")
    assert response.status_code == 200
    assert "refresh_token" not in response.json()
    assert "cli_refresh_id" not in decode_access_token(response.json()["access_token"])


async def test_password_change_revokes_cli_access_and_refresh(unauthenticated_client, cli_user):
    client = unauthenticated_client
    pending = start(client)
    tokens = exchange(client, pending, approve(client, cli_user, pending)["exchange_code"]).json()
    changed = client.put(
        "/api/auth/me/password",
        headers=bearer(cli_user),
        json={"current_password": "Cli-Password-123", "new_password": "Changed-Cli-Password-456"},
    )
    assert changed.status_code == 200, changed.text
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/cli/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )


async def test_session_version_change_immediately_rejects_existing_cli_access(
    unauthenticated_client, db_session, cli_user
):
    client = unauthenticated_client
    pending = start(client)
    tokens = exchange(client, pending, approve(client, cli_user, pending)["exchange_code"]).json()
    cli_user.session_version += 1
    await db_session.commit()
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        ).status_code
        == 401
    )


async def _session_ids(db_session):
    """Return the stored session ids as the hex strings SQLite keeps."""
    rows = await db_session.execute(text("SELECT id FROM cli_auth_sessions"))
    return set(rows.scalars())


async def _failures(db_session, action):
    """Return the failure audit events recorded for one action."""
    rows = await db_session.execute(
        select(AuditEvent)
        .where(AuditEvent.action == action, AuditEvent.outcome == "failure")
        .order_by(AuditEvent.id)
    )
    return list(rows.scalars())


async def test_start_deletes_expired_and_exchanged_sessions_and_keeps_live_ones(
    unauthenticated_client, db_session, cli_user
):
    client = unauthenticated_client
    expired = start(client)
    exchanged = start(client)
    approved = start(client)
    result = exchange(client, exchanged, approve(client, cli_user, exchanged)["exchange_code"])
    assert result.status_code == 200, result.text
    approve(client, cli_user, approved)
    await db_session.execute(
        text("UPDATE cli_auth_sessions SET expires_at = :expiry WHERE id = :id"),
        {
            "expiry": datetime.utcnow() - timedelta(seconds=1),
            "id": expired["session_id"].replace("-", ""),
        },
    )
    await db_session.commit()
    assert len(await _session_ids(db_session)) == 3
    fresh = start(client)
    assert await _session_ids(db_session) == {
        approved["session_id"].replace("-", ""),
        fresh["session_id"].replace("-", ""),
    }


async def test_failed_refresh_is_audited_without_the_token(
    unauthenticated_client, db_session, cli_user
):
    client = unauthenticated_client
    pending = start(client)
    tokens = exchange(client, pending, approve(client, cli_user, pending)["exchange_code"]).json()
    assert (
        client.post("/api/auth/cli/refresh", json={"refresh_token": tokens["refresh_token"]})
    ).status_code == 200
    replay = client.post("/api/auth/cli/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401
    assert replay.json() == {"detail": "Invalid or expired session"}
    [event] = await _failures(db_session, "auth.cli_refresh")
    assert event.details == {"reason": "invalid_token"}
    assert event.actor_type == "anonymous"
    assert tokens["refresh_token"] not in json.dumps(event.details)


async def test_refresh_for_a_deactivated_user_is_refused_audited_and_leaves_the_token(
    unauthenticated_client, db_session, cli_user
):
    client = unauthenticated_client
    pending = start(client)
    tokens = exchange(client, pending, approve(client, cli_user, pending)["exchange_code"]).json()
    cli_user.is_active = False
    await db_session.commit()
    response = client.post("/api/auth/cli/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401
    [event] = await _failures(db_session, "auth.cli_refresh")
    assert event.details == {"reason": "inactive_or_missing_user"}
    row = (
        await db_session.execute(
            select(UserToken).where(
                UserToken.token_hash == hashlib.sha256(tokens["refresh_token"].encode()).hexdigest()
            )
        )
    ).scalar_one()
    await db_session.refresh(row)
    assert row.used_at is None


async def test_cli_refresh_consumes_any_refresh_purpose_token_as_the_ticket_specifies(
    unauthenticated_client, cli_user
):
    client = unauthenticated_client
    login = client.post(
        "/api/auth/login", json={"email": cli_user.email, "password": "Cli-Password-123"}
    )
    assert login.status_code == 200
    browser_token = client.cookies.get("bud_refresh_token")
    rotated = client.post("/api/auth/cli/refresh", json={"refresh_token": browser_token})
    assert rotated.status_code == 200, rotated.text
    assert isinstance(decode_access_token(rotated.json()["access_token"])["cli_refresh_id"], int)
    assert client.post("/api/auth/refresh").status_code == 401
