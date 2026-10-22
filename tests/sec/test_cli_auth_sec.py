"""CLI authorization rejects invalid callbacks, proof keys, state and account changes."""

import base64
import hashlib
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, text

from app.api.auth import get_current_active_entity
from app.core.deps import limiter
from app.core.security import create_access_token
from app.models import AuditEvent, Runner, User, UserRole, UserToken, UserTokenPurpose

VERIFIER = "v" * 43
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
)
START = {"client_name": "CLI client", "mode": "code", "code_challenge": CHALLENGE, "state": "state"}
EXCHANGE_FAILURE_REASONS = {
    "pending": "unknown_or_unapproved_session",
    "bad_code": "code_or_verifier_mismatch",
    "bad_verifier": "code_or_verifier_mismatch",
    "expired": "expired_or_consumed",
    "disabled": "inactive_or_changed_user",
    "version": "inactive_or_changed_user",
}


@pytest.fixture(autouse=True)
def reset_limits(fresh_auth_rate_limits):
    """Reset authorization limits between cases."""


@pytest.fixture(autouse=True)
def code_sign_in_enabled(monkeypatch):
    """Turn code sign-in on for every case in this module."""
    monkeypatch.setattr("app.core.config.settings.CLI_CODE_MODE_ENABLED", True)


@pytest.fixture
async def cli_account(db_session):
    """Create a normal account and its existing JWT."""
    user = User(
        email="security-cli@example.com",
        full_name="CLI user",
        hashed_password="unused",
        role=UserRole.viewer,
        is_active=True,
        session_version=1,
    )
    db_session.add(user)
    await db_session.commit()
    headers = {
        "Authorization": "Bearer "
        + create_access_token({"sub": str(user.id), "type": "user", "ver": 1})
    }
    return user, headers


@pytest.mark.parametrize(
    "uri",
    [
        "https://127.0.0.1:1234/callback",
        "http://example.com:1234/callback",
        "http://127.0.0.2:1234/callback",
        "http://127.0.0.1/callback",
        "http://localhost:0/callback",
        "http://localhost:65536/callback",
        "http://user@localhost:1234/callback",
        "http://localhost:1234/callback#fragment",
        "http://localhost:1234/callback?code=old",
        "http://localhost:1234/callback?state=old",
        "http://localhost:1234/callback?%63ode=old",
        "http://localhost:1234/callback?CODE=old",
        "http://localhost.evil.test:1234/callback",
        "http://127.0.0.1:1234\\@evil.test/callback",
    ],
)
def test_non_loopback_or_ambiguous_callback_is_rejected(unauthenticated_client, uri):
    response = unauthenticated_client.post(
        "/api/auth/cli/start", json=START | {"mode": "callback", "redirect_uri": uri}
    )
    assert response.status_code == 422


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "[::1]"])
def test_exact_loopback_hosts_are_allowed(unauthenticated_client, host):
    response = unauthenticated_client.post(
        "/api/auth/cli/start",
        json=START | {"mode": "callback", "redirect_uri": f"http://{host}:1234/callback"},
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "changes",
    [
        {"code_challenge": "x" * 42},
        {"code_challenge": "+" * 43},
        {"code_challenge": "x" * 44},
        {"state": ""},
        {"mode": "poll"},
        {"mode": "callback"},
        {"redirect_uri": "http://localhost:1234/callback"},
        {"client_name": " "},
    ],
)
def test_invalid_start_fields_are_rejected(unauthenticated_client, changes):
    assert (
        unauthenticated_client.post("/api/auth/cli/start", json=START | changes).status_code == 422
    )


async def test_confirmation_requires_user_auth_and_cannot_be_approved_twice(
    unauthenticated_client, db_session, cli_account
):
    client = unauthenticated_client
    user, headers = cli_account
    pending = client.post("/api/auth/cli/start", json=START).json()
    session_id = pending["session_id"]
    assert client.get(f"/api/auth/cli/sessions/{session_id}").status_code == 401
    assert client.post("/api/auth/cli/approve", json={"session_id": session_id}).status_code == 401
    first = client.post("/api/auth/cli/approve", json={"session_id": session_id}, headers=headers)
    assert first.status_code == 200
    second = client.post("/api/auth/cli/approve", json={"session_id": session_id}, headers=headers)
    assert second.status_code in (400, 401)
    assert "exchange_code" not in second.json()
    [event] = (
        (
            await db_session.execute(
                select(AuditEvent).where(
                    AuditEvent.action == "auth.cli_approve", AuditEvent.outcome == "failure"
                )
            )
        )
        .scalars()
        .all()
    )
    assert event.details == {"reason": "not_pending"}
    assert event.actor_user_id == user.id
    assert event.target_id == session_id
    assert first.json()["exchange_code"] not in json.dumps(event.details)
    assert client.get(f"/api/auth/cli/sessions/{session_id}", headers=headers).status_code in (
        400,
        401,
    )


@pytest.mark.parametrize(
    "failure", ["pending", "bad_code", "bad_verifier", "expired", "disabled", "version"]
)
async def test_invalid_exchange_issues_no_tokens_or_success_audit(
    unauthenticated_client, db_session, cli_account, failure
):
    client = unauthenticated_client
    user, headers = cli_account
    pending = client.post("/api/auth/cli/start", json=START).json()
    session_id = pending["session_id"]
    code = "not-approved"
    if failure != "pending":
        code = client.post(
            "/api/auth/cli/approve", json={"session_id": session_id}, headers=headers
        ).json()["exchange_code"]
    if failure == "expired":
        await db_session.execute(
            text("UPDATE cli_auth_sessions SET expires_at = :expiry"),
            {"expiry": datetime.utcnow() - timedelta(seconds=1)},
        )
    if failure == "disabled":
        user.is_active = False
    if failure == "version":
        user.session_version += 1
    await db_session.commit()
    response = client.post(
        "/api/auth/cli/exchange",
        json={
            "session_id": session_id,
            "code": "wrong" if failure == "bad_code" else code,
            "code_verifier": "w" * 43 if failure == "bad_verifier" else VERIFIER,
        },
    )
    assert response.status_code in (400, 401), response.text
    assert "access_token" not in response.json()
    assert not list((await db_session.execute(select(UserToken))).scalars())
    assert not list(
        (
            await db_session.execute(
                select(AuditEvent).where(
                    AuditEvent.action == "auth.cli_exchange", AuditEvent.outcome == "success"
                )
            )
        ).scalars()
    )
    [event] = (
        (
            await db_session.execute(
                select(AuditEvent).where(
                    AuditEvent.action == "auth.cli_exchange", AuditEvent.outcome == "failure"
                )
            )
        )
        .scalars()
        .all()
    )
    assert event.details == {"reason": EXCHANGE_FAILURE_REASONS[failure]}
    assert event.actor_type == "anonymous"
    assert event.target_id == session_id
    for secret in (code, VERIFIER):
        assert secret not in json.dumps(event.details)


@pytest.mark.parametrize("verifier", ["v" * 42, "v" * 129, "!" * 43])
async def test_malformed_verifier_is_rejected(unauthenticated_client, verifier):
    response = unauthenticated_client.post(
        "/api/auth/cli/exchange",
        json={
            "session_id": "00000000-0000-0000-0000-000000000001",
            "code": "code",
            "code_verifier": verifier,
        },
    )
    assert response.status_code == 422


async def test_cli_claim_requires_a_live_refresh_row_for_the_same_user(db_session, cli_account):
    from fastapi import HTTPException

    user, _ = cli_account
    for refresh_id in (None, "invalid", 999999):
        jwt = create_access_token(
            {"sub": str(user.id), "type": "user", "ver": 1, "cli_refresh_id": refresh_id}
        )
        with pytest.raises(HTTPException) as error:
            await get_current_active_entity(token=jwt, db=db_session)
        assert error.value.status_code == 401


@pytest.mark.parametrize("condition", ["expired", "used", "wrong_user", "wrong_purpose"])
async def test_cli_claim_rejects_invalid_refresh_bindings(db_session, cli_account, condition):
    from fastapi import HTTPException

    user, _ = cli_account
    owner = user
    if condition == "wrong_user":
        owner = User(
            email="other-cli@example.com",
            full_name="Other",
            hashed_password="unused",
            role=UserRole.viewer,
            is_active=True,
        )
        db_session.add(owner)
        await db_session.flush()
    row = UserToken(
        user_id=owner.id,
        purpose=(
            UserTokenPurpose.invite if condition == "wrong_purpose" else UserTokenPurpose.refresh
        ),
        token_hash="a" * 64,
        expires_at=datetime.utcnow() + timedelta(minutes=-1 if condition == "expired" else 1),
        used_at=datetime.utcnow() if condition == "used" else None,
    )
    db_session.add(row)
    await db_session.commit()
    token = create_access_token(
        {"sub": str(user.id), "type": "user", "ver": 1, "cli_refresh_id": row.id}
    )
    with pytest.raises(HTTPException) as error:
        await get_current_active_entity(token=token, db=db_session)
    assert error.value.status_code == 401


async def test_runner_jwt_authentication_is_unchanged(db_session):
    runner = Runner(
        account="cli-test-station", password_hash="unused", token="station-token", is_active=True
    )
    db_session.add(runner)
    await db_session.commit()
    token = create_access_token({"sub": runner.account, "type": "runner"})
    assert await get_current_active_entity(token=token, db=db_session) is runner


@pytest.mark.parametrize(
    "path,body",
    [
        ("start", START),
        (
            "exchange",
            {
                "session_id": "00000000-0000-0000-0000-000000000001",
                "code": "invalid",
                "code_verifier": VERIFIER,
            },
        ),
        ("refresh", {"refresh_token": "invalid"}),
    ],
)
def test_public_cli_routes_are_rate_limited(unauthenticated_client, path, body):
    statuses = [
        unauthenticated_client.post(f"/api/auth/cli/{path}", json=body).status_code
        for _ in range(31)
    ]
    assert 429 in statuses
    assert limiter.enabled


@pytest.mark.parametrize("mode", ["callback", "code"])
async def test_deny_requires_a_signed_in_account_and_keeps_the_request(
    unauthenticated_client, db_session, cli_account, mode
):
    client = unauthenticated_client
    _, headers = cli_account
    body = START | (
        {"mode": "callback", "redirect_uri": "http://127.0.0.1:1234/callback"}
        if mode == "callback"
        else {}
    )
    session_id = client.post("/api/auth/cli/start", json=body).json()["session_id"]
    assert client.post("/api/auth/cli/deny", json={"session_id": session_id}).status_code == 401
    runner = create_access_token({"sub": "cli-test-station", "type": "runner"})
    assert client.post(
        "/api/auth/cli/deny",
        json={"session_id": session_id},
        headers={"Authorization": f"Bearer {runner}"},
    ).status_code in (401, 403)
    stored = (await db_session.execute(text("SELECT id FROM cli_auth_sessions"))).scalars().all()
    assert stored == [session_id.replace("-", "")]
    assert client.get(f"/api/auth/cli/sessions/{session_id}", headers=headers).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"session_id": "invalid"},
        {"session_id": "00000000-0000-0000-0000-000000000001", "extra": "field"},
    ],
)
def test_deny_rejects_malformed_bodies(unauthenticated_client, cli_account, body):
    _, headers = cli_account
    response = unauthenticated_client.post("/api/auth/cli/deny", json=body, headers=headers)
    assert response.status_code == 422


def test_deny_is_not_rate_limited(unauthenticated_client, cli_account):
    _, headers = cli_account
    statuses = {
        unauthenticated_client.post(
            "/api/auth/cli/deny",
            json={"session_id": "00000000-0000-0000-0000-000000000001"},
            headers=headers,
        ).status_code
        for _ in range(31)
    }
    assert statuses == {400}
