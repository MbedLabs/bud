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
    assert boss_mail[0]["review_link"].endswith("/access")
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


async def test_reviewers_see_each_requesters_picture_and_no_other_identity_is_disclosed(
    unauthenticated_client, db_session, sent_mail, fresh_auth_rate_limits
):
    admin_id = await _user(db_session, "picture-admin@example.com", UserRole.admin)
    first_id = await _user(db_session, "picture-first@example.com")
    second_id = await _user(db_session, "picture-second@example.com")
    for user_id, picture in ((admin_id, b"admin"), (first_id, b"first"), (second_id, b"second")):
        user = await db_session.get(User, user_id)
        user.profile_picture = picture
    await db_session.commit()
    admin_headers = _login(unauthenticated_client, "picture-admin@example.com")
    first_headers = _login(unauthenticated_client, "picture-first@example.com")
    second_headers = _login(unauthenticated_client, "picture-second@example.com")
    for headers in (first_headers, second_headers):
        created = unauthenticated_client.post("/api/access-requests", json=REQUEST, headers=headers)
        assert created.status_code == 201
        assert created.json()["requester_profile_picture_url"] is None
        mine = unauthenticated_client.get("/api/access-requests/mine", params=REQUEST, headers=headers)
        assert mine.status_code == 200
        assert mine.json()["requester_profile_picture_url"] is None
        assert unauthenticated_client.get("/api/access-requests", headers=headers).status_code == 403
    assert unauthenticated_client.get("/api/access-requests").status_code == 401
    for picture in (b"first", b"replacement", None):
        first = await db_session.get(User, first_id)
        first.profile_picture = picture
        await db_session.commit()
        response = unauthenticated_client.get("/api/access-requests", headers=admin_headers)
        assert response.status_code == 200
        requesters = {item["requester_email"]: item for item in response.json()}
        second = await db_session.get(User, second_id)
        admin = await db_session.get(User, admin_id)
        assert requesters[first.email]["requester_profile_picture_url"] == first.profile_picture_url
        assert requesters[second.email]["requester_profile_picture_url"] == second.profile_picture_url
        assert requesters[second.email]["requester_profile_picture_url"] != admin.profile_picture_url
