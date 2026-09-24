"""The audit log records security-relevant events with who, where and the outcome."""

import json

from fastapi.routing import APIRoute
from sqlalchemy import select

from app.core.security import get_password_hash
from app.main import app
from app.models import AuditEvent
from app.models.user import User, UserRole

PASSWORD = "Correct-Horse-Battery-9"


async def _user(db_session, email, role=UserRole.viewer):
    user = User(
        email=email,
        full_name=email.split("@")[0],
        hashed_password=get_password_hash(PASSWORD),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _events(db_session, action):
    rows = await db_session.execute(
        select(AuditEvent).where(AuditEvent.action == action).order_by(AuditEvent.id)
    )
    return list(rows.scalars())


def _login(client, email):
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_a_failed_login_is_recorded_although_the_request_fails(
    unauthenticated_client, db_session
):
    user = await _user(db_session, "someone@example.com")

    response = unauthenticated_client.post(
        "/api/auth/login",
        json={"email": "someone@example.com", "password": "wrong-password-1"},
        headers={"user-agent": "audit-test/1.0"},
    )

    assert response.status_code == 401
    [event] = await _events(db_session, "auth.login")
    assert event.outcome == "failure"
    assert event.actor_type == "anonymous"
    assert event.target_id == str(user.id)
    assert event.request_id == response.headers["x-request-id"]
    assert event.user_agent == "audit-test/1.0"
    assert "wrong-password-1" not in json.dumps(event.details)


async def test_a_deactivation_records_the_admin(unauthenticated_client, db_session):
    admin = await _user(db_session, "boss@example.com", UserRole.admin)
    member = await _user(db_session, "member@example.com")
    headers = _login(unauthenticated_client, "boss@example.com")

    response = unauthenticated_client.patch(
        f"/api/users/{member.id}", json={"is_active": False}, headers=headers
    )

    assert response.status_code == 200, response.text
    [event] = await _events(db_session, "user.deactivated")
    assert event.actor_type == "user" and event.actor_user_id == admin.id
    assert event.target_id == str(member.id)


async def test_an_enrolment_key_is_recorded_without_the_key(unauthenticated_client, db_session):
    await _user(db_session, "boss@example.com", UserRole.admin)
    headers = _login(unauthenticated_client, "boss@example.com")

    minted = unauthenticated_client.post(
        "/api/runners/api-keys", json={"label": "Bench key"}, headers=headers
    )
    revoked = unauthenticated_client.delete(
        f"/api/runners/api-keys/{minted.json()['id']}", headers=headers
    )

    assert (minted.status_code, revoked.status_code) == (201, 204)
    [mint] = await _events(db_session, "enrolment_key.minted")
    [revoke] = await _events(db_session, "enrolment_key.revoked")
    assert mint.details["label"] == "Bench key"
    assert minted.json()["api_key"] not in json.dumps(mint.details)
    assert revoke.target_id == str(minted.json()["id"])


async def test_only_administrators_read_the_audit_log(unauthenticated_client, db_session):
    await _user(db_session, "boss@example.com", UserRole.admin)
    await _user(db_session, "member@example.com")
    member_headers = _login(unauthenticated_client, "member@example.com")
    admin_headers = _login(unauthenticated_client, "boss@example.com")

    refused = unauthenticated_client.get("/api/audit", headers=member_headers)
    page = unauthenticated_client.get(
        "/api/audit", params={"action": "auth."}, headers=admin_headers
    )

    assert refused.status_code == 403
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 2
    assert {item["action"] for item in body["items"]} == {"auth.login"}
    assert body["items"][0]["actor_name"] == "boss"


def _api_routes(routes):
    """Yield every API route, including those of included routers."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from _api_routes(included.routes)


def test_no_endpoint_changes_or_deletes_an_audit_event():
    methods = {
        method
        for route in _api_routes(app.routes)
        if route.endpoint.__module__ == "app.api.audit"
        for method in route.methods
    }

    assert methods == {"GET"}
