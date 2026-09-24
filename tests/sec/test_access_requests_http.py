"""A refused user asks the administrators for access, once per resource per day."""

import pytest
from sqlalchemy import select

from app.api import access_requests as access_requests_api
from app.core.security import get_password_hash
from app.models import AuditEvent
from app.models.user import User, UserRole

PASSWORD = "Correct-Horse-Battery-9"
REQUEST = {"resource_type": "test-run", "resource_ref": "42"}


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
    return user.id


def _login(client, email):
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def sent_mail(monkeypatch):
    """Capture the access request emails instead of sending them."""
    sent = []
    monkeypatch.setattr(
        access_requests_api, "send_access_request_email", lambda **kwargs: sent.append(kwargs)
    )
    return sent


async def test_a_request_emails_the_administrators_once_a_day(
    unauthenticated_client, db_session, sent_mail
):
    await _user(db_session, "boss@example.com", UserRole.admin)
    await _user(db_session, "member@example.com")
    headers = _login(unauthenticated_client, "member@example.com")

    first = unauthenticated_client.post("/api/access-requests", json=REQUEST, headers=headers)
    again = unauthenticated_client.post("/api/access-requests", json=REQUEST, headers=headers)
    mine = unauthenticated_client.get("/api/access-requests/mine", params=REQUEST, headers=headers)

    assert first.status_code == 201, first.text
    assert first.json()["mail_sent"] is True
    assert again.status_code == 200 and again.json()["already_requested"] is True
    assert mine.json()["id"] == first.json()["id"]
    boss_mail = [mail for mail in sent_mail if mail["to_email"] == "boss@example.com"]
    assert len(boss_mail) == 1
    assert boss_mail[0]["review_link"].endswith("/users")
    assert boss_mail[0]["request_id"] == first.headers["x-request-id"]
    events = (
        (
            await db_session.execute(
                select(AuditEvent).where(AuditEvent.action == "access.requested")
            )
        )
        .scalars()
        .all()
    )
    assert [(e.target_type, e.target_id) for e in events] == [("test-run", "42")]


async def test_an_administrator_decision_is_recorded_once(
    unauthenticated_client, db_session, sent_mail
):
    await _user(db_session, "boss@example.com", UserRole.admin)
    member_id = await _user(db_session, "member@example.com")
    member_headers = _login(unauthenticated_client, "member@example.com")
    admin_headers = _login(unauthenticated_client, "boss@example.com")
    created = unauthenticated_client.post(
        "/api/access-requests", json=REQUEST, headers=member_headers
    ).json()

    listed = unauthenticated_client.get("/api/access-requests", headers=admin_headers)
    by_member = unauthenticated_client.post(
        f"/api/access-requests/{created['id']}/decision",
        json={"decision": "refused"},
        headers=member_headers,
    )
    refused = unauthenticated_client.post(
        f"/api/access-requests/{created['id']}/decision",
        json={"decision": "refused"},
        headers=admin_headers,
    )
    twice = unauthenticated_client.post(
        f"/api/access-requests/{created['id']}/decision",
        json={"decision": "granted"},
        headers=admin_headers,
    )

    assert [r["requester_email"] for r in listed.json()] == ["member@example.com"]
    assert by_member.status_code == 403
    assert refused.status_code == 200 and refused.json()["status"] == "refused"
    assert twice.status_code == 409
    event = (
        await db_session.execute(select(AuditEvent).where(AuditEvent.action == "access.refused"))
    ).scalar_one()
    assert event.details["requester_user_id"] == member_id


async def test_an_anonymous_client_cannot_request(unauthenticated_client):
    response = unauthenticated_client.post("/api/access-requests", json=REQUEST)

    assert response.status_code == 401


async def test_only_known_resource_types_are_accepted(
    unauthenticated_client, db_session, sent_mail
):
    await _user(db_session, "member@example.com")
    headers = _login(unauthenticated_client, "member@example.com")

    response = unauthenticated_client.post(
        "/api/access-requests",
        json={"resource_type": "user", "resource_ref": "1"},
        headers=headers,
    )

    assert response.status_code == 422
