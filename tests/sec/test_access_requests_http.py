"""A user without Publish to Bloom asks the administrators for it, once per run per day."""

import pytest
from sqlalchemy import func, select

from app.api import access_requests as access_requests_api
from app.core.security import get_password_hash
from app.models import (
    AccessGroup,
    AccessGroupMember,
    AccessRequest,
    AuditEvent,
    Product,
)
from app.models import TestRun as RunModel
from app.models.user import User, UserRole

PASSWORD = "Correct-Horse-Battery-9"
RUN_NAME = "Nightly smoke"

pytestmark = pytest.mark.usefixtures("fresh_auth_rate_limits")


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


async def _run(db_session, name=RUN_NAME):
    """Store a completed run and return its id."""
    run = RunModel(name=name, test_case_list="suite", status="Completed")
    db_session.add(run)
    await db_session.commit()
    return run.id


async def _request(db_session):
    """A Publish to Bloom request asked from a stored run."""
    return {"resource_type": "publish-to-bloom", "resource_ref": str(await _run(db_session))}


async def _give(db_session, user_id, system_key):
    """Give the user the shipped group with this system key."""
    group = (
        await db_session.execute(select(AccessGroup).where(AccessGroup.system_key == system_key))
    ).scalar_one()
    db_session.add(AccessGroupMember(group_id=group.id, user_id=user_id))
    await db_session.commit()


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
    body = await _request(db_session)

    first = unauthenticated_client.post("/api/access-requests", json=body, headers=headers)
    again = unauthenticated_client.post("/api/access-requests", json=body, headers=headers)
    mine = unauthenticated_client.get("/api/access-requests/mine", params=body, headers=headers)

    assert first.status_code == 201, first.text
    assert first.json()["mail_sent"] is True
    assert again.status_code == 200
    assert again.json()["already_requested"] is True
    assert mine.json()["id"] == first.json()["id"]
    boss_mail = [mail for mail in sent_mail if mail["to_email"] == "boss@example.com"]
    assert len(boss_mail) == 1
    assert boss_mail[0]["review_link"].endswith("/access")
    assert boss_mail[0]["request_id"] == first.headers["x-request-id"]
    assert boss_mail[0]["resource"] == (
        f"Publish to Bloom (from test run {body['resource_ref']}: {RUN_NAME})"
    )
    events = (
        (
            await db_session.execute(
                select(AuditEvent).where(AuditEvent.action == "access.requested")
            )
        )
        .scalars()
        .all()
    )
    assert [(e.target_type, e.target_id) for e in events] == [
        ("publish-to-bloom", body["resource_ref"])
    ]


async def test_an_administrator_decision_is_recorded_once(
    unauthenticated_client, db_session, sent_mail
):
    await _user(db_session, "boss@example.com", UserRole.admin)
    member_id = await _user(db_session, "member@example.com")
    member_headers = _login(unauthenticated_client, "member@example.com")
    admin_headers = _login(unauthenticated_client, "boss@example.com")
    body = await _request(db_session)
    created = unauthenticated_client.post(
        "/api/access-requests", json=body, headers=member_headers
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
    assert [(r["resource_label"], r["resource_deleted"]) for r in listed.json()] == [
        (RUN_NAME, False)
    ]
    assert by_member.status_code == 403
    assert refused.status_code == 200
    assert refused.json()["status"] == "refused"
    assert twice.status_code == 409
    event = (
        await db_session.execute(select(AuditEvent).where(AuditEvent.action == "access.refused"))
    ).scalar_one()
    assert event.details["requester_user_id"] == member_id


async def test_an_anonymous_client_cannot_request(unauthenticated_client):
    response = unauthenticated_client.post(
        "/api/access-requests", json={"resource_type": "publish-to-bloom", "resource_ref": "1"}
    )

    assert response.status_code == 401


async def test_only_known_resource_types_are_accepted(
    unauthenticated_client, db_session, sent_mail
):
    await _user(db_session, "member@example.com")
    headers = _login(unauthenticated_client, "member@example.com")

    for resource_type in ("user", "test-run", "product"):
        params = {"resource_type": resource_type, "resource_ref": "1"}
        created = unauthenticated_client.post("/api/access-requests", json=params, headers=headers)
        mine = unauthenticated_client.get(
            "/api/access-requests/mine", params=params, headers=headers
        )

        assert created.status_code == 422, resource_type
        assert mine.status_code == 422, resource_type
    assert sent_mail == []


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
    body = await _request(db_session)
    first_headers = _login(unauthenticated_client, "picture-first@example.com")
    second_headers = _login(unauthenticated_client, "picture-second@example.com")
    for headers in (first_headers, second_headers):
        created = unauthenticated_client.post("/api/access-requests", json=body, headers=headers)
        assert created.status_code == 201
        assert created.json()["requester_profile_picture_url"] is None
        mine = unauthenticated_client.get("/api/access-requests/mine", params=body, headers=headers)
        assert mine.status_code == 200
        assert mine.json()["requester_profile_picture_url"] is None
        assert (
            unauthenticated_client.get("/api/access-requests", headers=headers).status_code == 403
        )
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
        assert (
            requesters[second.email]["requester_profile_picture_url"] == second.profile_picture_url
        )
        assert (
            requesters[second.email]["requester_profile_picture_url"] != admin.profile_picture_url
        )


@pytest.mark.parametrize(
    ("role", "group"),
    [
        (UserRole.admin, None),
        (UserRole.developer, None),
        (UserRole.viewer, "test_operators"),
        (UserRole.viewer, "app_administration"),
    ],
)
async def test_someone_who_holds_publish_to_bloom_is_refused_and_nobody_is_mailed(
    unauthenticated_client, db_session, sent_mail, role, group
):
    await _user(db_session, "boss@example.com", UserRole.admin)
    holder_id = await _user(db_session, "holder@example.com", role)
    if group:
        await _give(db_session, holder_id, group)
    headers = _login(unauthenticated_client, "holder@example.com")
    request = await _request(db_session)

    created = unauthenticated_client.post("/api/access-requests", json=request, headers=headers)

    assert created.status_code == 409, created.text
    assert created.json()["detail"] == access_requests_api.ALREADY_HELD
    assert sent_mail == []
    assert await db_session.scalar(select(func.count()).select_from(AccessRequest)) == 0
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "access.requested")
        )
        == 0
    )


async def test_a_holders_earlier_pending_request_does_not_answer_a_new_one(
    unauthenticated_client, db_session, sent_mail
):
    member_id = await _user(db_session, "member@example.com")
    headers = _login(unauthenticated_client, "member@example.com")
    request = await _request(db_session)
    assert (
        unauthenticated_client.post(
            "/api/access-requests", json=request, headers=headers
        ).status_code
        == 201
    )
    await _give(db_session, member_id, "test_operators")

    again = unauthenticated_client.post("/api/access-requests", json=request, headers=headers)

    assert again.status_code == 409, again.text


async def test_the_requester_is_never_mailed_about_their_own_request(
    unauthenticated_client, db_session, sent_mail
):
    await _user(db_session, "boss@example.com", UserRole.admin)
    manager_id = await _user(db_session, "manager@example.com")
    await _give(db_session, manager_id, "access_managers")
    headers = _login(unauthenticated_client, "manager@example.com")

    created = unauthenticated_client.post(
        "/api/access-requests", json=await _request(db_session), headers=headers
    )

    assert created.status_code == 201, created.text
    recipients = [mail["to_email"] for mail in sent_mail]
    assert "boss@example.com" in recipients
    assert "manager@example.com" not in recipients


async def test_stored_requests_of_earlier_types_stay_listed_named_and_decidable(
    unauthenticated_client, db_session, sent_mail
):
    await _user(db_session, "boss@example.com", UserRole.admin)
    member_id = await _user(db_session, "member@example.com")
    run_id = await _run(db_session)
    product = Product(name="Gateway board")
    gone = RunModel(name="Removed run", test_case_list="suite", status="Completed")
    db_session.add_all([product, gone])
    await db_session.commit()
    gone_id = gone.id
    await db_session.delete(gone)
    rows = [
        AccessRequest(user_id=member_id, resource_type="test-run", resource_ref=str(run_id)),
        AccessRequest(user_id=member_id, resource_type="product", resource_ref=str(product.id)),
        AccessRequest(
            user_id=member_id, resource_type="publish-to-bloom", resource_ref=str(gone_id)
        ),
    ]
    db_session.add_all(rows)
    await db_session.commit()
    headers = _login(unauthenticated_client, "boss@example.com")

    listed = unauthenticated_client.get("/api/access-requests", headers=headers)
    refused = unauthenticated_client.post(
        f"/api/access-requests/{rows[0].id}/decision",
        json={"decision": "refused"},
        headers=headers,
    )

    assert listed.status_code == 200, listed.text
    named = {
        row["resource_type"]: (row["resource_ref"], row["resource_label"], row["resource_deleted"])
        for row in listed.json()
    }
    assert named == {
        "test-run": (str(run_id), RUN_NAME, False),
        "product": (str(product.id), "Gateway board", False),
        "publish-to-bloom": (str(gone_id), None, True),
    }
    assert refused.status_code == 200, refused.text
    assert (refused.json()["status"], refused.json()["resource_label"]) == ("refused", RUN_NAME)
