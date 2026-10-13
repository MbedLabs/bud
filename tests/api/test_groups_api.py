"""Access over HTTP: base roles, policies, groups as bundles of policies, and who gives what.

A user's access is their base role's allowance plus the policies of every group they have.
Default policies and groups are read-only; an Admin edits policies; access management gives
only groups whose policies the giver holds; groups hide nothing.
"""

from datetime import datetime

import pytest

from app.api import access_requests as access_requests_api
from app.api.auth import get_current_active_entity, get_current_user
from app.main import app
from app.models import Artifact, Product, Runner
from app.models import TestRun as RunModel
from app.models.access import AccessGroup, AccessGroupMember, Policy
from app.models.user import User, UserRole

ADMIN = User(
    id=1,
    email="tester@example.com",
    full_name="Tester",
    hashed_password="x",
    role=UserRole.admin,
    is_active=True,
    session_version=1,
)

DEFAULT_GROUPS = [
    "Application Administrators",
    "Access Managers",
    "Results Viewers",
    "Station Managers",
    "Test Operators",
]


def _user(email, name, role):
    return User(
        email=email,
        full_name=name,
        hashed_password="x",
        role=role,
        is_active=True,
        session_version=1,
    )


async def _seed(db_session):
    first = Product(name="Gateway")
    second = Product(name="Sensor")
    viewer = _user("viewer@example.com", "Val Viewer", UserRole.viewer)
    developer = _user("dev@example.com", "Dee Developer", UserRole.developer)
    station = Runner(account="bench-1", password_hash="x", token="t", socket_port=53100)
    db_session.add_all([first, second, viewer, developer, station])
    await db_session.flush()
    runs = [
        RunModel(
            name="gateway-suite",
            test_case_list="a",
            status="Running",
            product_id=first.id,
            runner_id=station.id,
            started_at=datetime.utcnow(),
        ),
        RunModel(name="sensor-suite", test_case_list="b", status="Completed", product_id=second.id),
        RunModel(name="loose-suite", test_case_list="c", status="Completed"),
    ]
    db_session.add_all(runs)
    await db_session.flush()
    artifact = Artifact(
        filename="log.txt",
        original_filename="log.txt",
        content_type="text/plain",
        size_bytes=3,
        storage_path="log.txt",
        test_run_id=runs[1].id,
    )
    db_session.add(artifact)
    await db_session.commit()
    return first, second, viewer, developer, runs, artifact


def _as(user):
    async def current():
        return user

    app.dependency_overrides[get_current_user] = current
    app.dependency_overrides[get_current_active_entity] = current


def _group_id(client, name):
    return next(g["id"] for g in client.get("/api/groups").json() if g["name"] == name)


def _policy_id(client, name):
    return next(p["id"] for p in client.get("/api/policies").json() if p["name"] == name)


def _give(client, group, user):
    return client.post(f"/api/groups/{_group_id(client, group)}/members", json={"user_id": user.id})


@pytest.mark.asyncio
async def test_defaults_ship_and_are_read_only(client, db_session):
    groups = client.get("/api/groups").json()
    assert sorted(g["name"] for g in groups) == sorted(DEFAULT_GROUPS)
    assert all(g["is_default"] for g in groups)
    bundles = {g["name"]: sorted(p["name"] for p in g["policies"]) for g in groups}
    assert bundles["Results Viewers"] == ["Results"]
    assert bundles["Test Operators"] == ["Custom runs", "Publish to Bloom", "Results"]
    assert bundles["Station Managers"] == ["Results", "Stations"]
    assert bundles["Access Managers"] == ["Access management", "Results", "Stations"]
    assert len(bundles["Application Administrators"]) == 8
    policies = client.get("/api/policies").json()
    assert [p["name"] for p in policies] == [
        "Results",
        "Custom runs",
        "Publish to Bloom",
        "Stations",
        "Products",
        "Settings and integrations",
        "Audit log",
        "Access management",
    ]
    assert all(p["is_default"] for p in policies)

    operators = _group_id(client, "Test Operators")
    assert client.patch(f"/api/groups/{operators}", json={"name": "X"}).status_code == 409
    assert client.delete(f"/api/groups/{operators}").status_code == 409
    results = _policy_id(client, "Results")
    assert client.patch(f"/api/policies/{results}", json={"name": "X"}).status_code == 409
    assert client.delete(f"/api/policies/{results}").status_code == 409

    copy = client.post(f"/api/groups/{operators}/duplicate")
    assert copy.status_code == 201, copy.text
    assert (copy.json()["name"], copy.json()["is_default"], copy.json()["members"]) == (
        "Test Operators (copy)",
        False,
        [],
    )
    assert client.patch(f"/api/groups/{copy.json()['id']}", json={"name": "Night shift"}).json()[
        "name"
    ] == "Night shift"
    policy_copy = client.post(f"/api/policies/{results}/duplicate").json()
    assert (policy_copy["name"], policy_copy["is_default"]) == ("Results (copy)", False)


@pytest.mark.asyncio
async def test_custom_groups_bundle_policies(client, db_session):
    _, _, viewer, _, _, _ = await _seed(db_session)
    ids = [_policy_id(client, "Results"), _policy_id(client, "Custom runs")]
    created = client.post("/api/groups", json={"name": "Lab", "policy_ids": ids})
    assert created.status_code == 201, created.text
    group_id = created.json()["id"]
    assert created.json()["permissions"] == [
        "custom_runs.create",
        "evidence.view",
        "products.view",
        "reports.export",
        "stations.view",
    ]
    assert client.post("/api/groups", json={"name": "Lab"}).status_code == 409
    assert client.post("/api/groups", json={"name": "Bad", "policy_ids": [999]}).status_code == 422

    member = client.post(f"/api/groups/{group_id}/members", json={"user_id": viewer.id})
    assert member.status_code == 201
    assert member.json()["members"] == [
        {"user_id": viewer.id, "email": "viewer@example.com", "full_name": "Val Viewer", "role": "viewer", "profile_picture_url": None}
    ]
    assert client.post(f"/api/groups/{group_id}/members", json={"user_id": viewer.id}).status_code == 409
    assert client.post(f"/api/groups/{group_id}/members", json={"user_id": 999}).status_code == 404

    changed = client.patch(
        f"/api/groups/{group_id}",
        json={"name": "Lab A", "description": "Bench", "policy_ids": [ids[0]]},
    )
    assert (changed.json()["name"], changed.json()["description"]) == ("Lab A", "Bench")
    assert [p["name"] for p in changed.json()["policies"]] == ["Results"]
    client.post("/api/groups", json={"name": "Other"})
    assert client.patch(f"/api/groups/{group_id}", json={"name": "Other"}).status_code == 409

    assert client.delete(f"/api/groups/{group_id}/members/{viewer.id}").json()["members"] == []
    assert client.delete(f"/api/groups/{group_id}/members/{viewer.id}").status_code == 404
    assert client.delete(f"/api/groups/{group_id}").status_code == 204
    assert client.delete(f"/api/groups/{group_id}").status_code == 404


@pytest.mark.parametrize(
    "payload",
    [{"role": "admin"}, {"permission": "write"}, {"product_ids": [1]}, {"policy_ids": "x"}],
)
def test_group_contract_refuses_unknown_inputs(client, payload):
    response = client.post("/api/groups", json={"name": "Invalid", **payload})
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_policies_are_edited_by_an_admin_against_the_catalogue(client, db_session):
    catalogue = {row["resource"]: row["actions"] for row in client.get("/api/policies/catalogue").json()}
    assert catalogue["stations"] == ["view", "manage"]
    assert catalogue["access"] == ["manage"]
    created = client.post(
        "/api/policies",
        json={"name": "Station keys", "permissions": {"stations": ["manage", "view"]}},
    )
    assert created.status_code == 201, created.text
    assert created.json()["permissions"] == {"stations": ["view", "manage"]}
    assert client.post("/api/policies", json={"name": "Station keys"}).status_code == 409
    assert (
        client.post("/api/policies", json={"name": "Bad", "permissions": {"users": ["edit"]}}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/policies", json={"name": "Bad", "permissions": {"stations": ["delete"]}}
        ).status_code
        == 422
    )
    policy_id = created.json()["id"]
    group = client.post("/api/groups", json={"name": "Keys", "policy_ids": [policy_id]}).json()
    assert client.delete(f"/api/policies/{policy_id}").status_code == 409
    client.delete(f"/api/groups/{group['id']}")
    assert client.delete(f"/api/policies/{policy_id}").status_code == 204


@pytest.mark.asyncio
async def test_base_role_plus_every_group_decides(client, db_session):
    _, _, viewer, _, runs, _ = await _seed(db_session)
    _give(client, "Results Viewers", viewer)

    _as(viewer)
    me = client.get("/api/auth/me").json()
    assert me["role"] == "viewer"
    assert "custom_runs.create" not in me["permissions"]
    assert client.post("/api/test-runs/custom", json={"test_paths": ["a.B"]}).status_code == 403

    _as(ADMIN)
    _give(client, "Test Operators", viewer)
    _as(viewer)
    me = client.get("/api/auth/me").json()
    assert me["role"] == "viewer"
    assert {"custom_runs.create", "bloom_publish.execute"} <= set(me["permissions"])
    queued = client.post("/api/test-runs/custom", json={"test_paths": ["a.B"]})
    assert queued.status_code == 422, queued.text
    assert queued.json()["detail"].startswith("None of the selected test cases can be run")
    assert client.delete(f"/api/test-runs/{runs[1].id}").status_code == 403
    assert client.get("/api/groups").status_code == 403

    _as(ADMIN)
    client.delete(f"/api/groups/{_group_id(client, 'Test Operators')}/members/{viewer.id}")
    _as(viewer)
    assert "custom_runs.create" not in client.get("/api/auth/me").json()["permissions"]
    assert client.post("/api/test-runs/custom", json={"test_paths": ["a.B"]}).status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.admin, UserRole.developer, UserRole.viewer])
@pytest.mark.parametrize("group_name", ["Station Managers", "Access Managers", "Application Administrators"])
async def test_station_group_recipients_follow_role_hierarchy(client, db_session, role, group_name):
    """Station-group assignments preserve accounts and accept Admin or Developer recipients."""
    recipient = _user("recipient@example.com", "Recipient", role)
    db_session.add(recipient)
    await db_session.commit()
    account = (recipient.id, recipient.email, recipient.full_name, recipient.role, recipient.is_active)
    group_id = _group_id(client, group_name)
    response = client.post(f"/api/groups/{group_id}/members", json={"user_id": recipient.id})
    membership_key = {"group_id": group_id, "user_id": recipient.id}

    if role == UserRole.viewer:
        assert response.status_code == 422, response.text
        assert await db_session.get(AccessGroupMember, membership_key) is None
    else:
        assert response.status_code == 201, response.text
        assert response.json()["members"] == [
            {
                "user_id": recipient.id,
                "email": recipient.email,
                "full_name": recipient.full_name,
                "role": role.value,
                "profile_picture_url": None,
            }
        ]
        assert await db_session.get(AccessGroupMember, membership_key) is not None
        removed = client.delete(f"/api/groups/{group_id}/members/{recipient.id}")
        assert removed.status_code == 200, removed.text
        assert removed.json()["members"] == []
        db_session.expire_all()
        assert await db_session.get(AccessGroupMember, membership_key) is None

    unchanged = await db_session.get(User, account[0], populate_existing=True)
    assert unchanged is not None
    assert (
        unchanged.id, unchanged.email, unchanged.full_name, unchanged.role, unchanged.is_active
    ) == account


@pytest.mark.asyncio
async def test_access_managers_give_only_what_they_hold(client, db_session):
    _, _, viewer, developer, _, _ = await _seed(db_session)
    assert _give(client, "Access Managers", viewer).status_code == 422
    assert _give(client, "Station Managers", viewer).status_code == 422
    assert _give(client, "Access Managers", developer).status_code == 201

    _as(developer)
    assert client.get("/api/groups").status_code == 200
    assert client.get("/api/policies").status_code == 200
    users = {u["email"]: u for u in client.get("/api/access/users").json()}
    assert users["dev@example.com"]["groups"] == [
        {"id": _group_id(client, "Access Managers"), "name": "Access Managers"}
    ]
    assert "access.manage" in users["dev@example.com"]["permissions"]
    assert users["viewer@example.com"]["permissions"] == [
        "evidence.view",
        "products.view",
        "reports.export",
        "stations.view",
    ]

    assert _give(client, "Test Operators", viewer).status_code == 201
    assert _give(client, "Application Administrators", viewer).status_code == 403
    assert _give(client, "Application Administrators", developer).status_code == 403

    products = _policy_id(client, "Products")
    settings = _policy_id(client, "Settings and integrations")
    assert client.post("/api/groups", json={"name": "P", "policy_ids": [products]}).status_code == 403
    own = client.post(
        "/api/groups",
        json={"name": "Bench crew", "policy_ids": [_policy_id(client, "Stations")]},
    )
    assert own.status_code == 201, own.text
    assert (
        client.patch(f"/api/groups/{own.json()['id']}", json={"policy_ids": [settings]}).status_code
        == 403
    )

    assert client.post("/api/policies", json={"name": "Mine"}).status_code == 403
    assert client.get("/api/users").status_code == 403
    assert client.post("/api/users/invite", json={"email": "x@example.com", "full_name": "X"}).status_code == 403

    _as(ADMIN)
    assert _give(client, "Application Administrators", developer).status_code == 201
    _as(developer)
    assert _give(client, "Application Administrators", developer).status_code == 403
    assert (
        client.delete(
            f"/api/groups/{_group_id(client, 'Application Administrators')}/members/{developer.id}"
        ).status_code
        == 403
    )


@pytest.mark.asyncio
async def test_groups_hide_nothing(client, db_session):
    first, second, viewer, _, runs, artifact = await _seed(db_session)
    _give(client, "Results Viewers", viewer)

    _as(viewer)
    names = sorted(r["name"] for r in client.get("/api/test-runs").json()["runs"])
    assert names == ["gateway-suite", "loose-suite", "sensor-suite"]
    for run in runs:
        assert client.get(f"/api/test-runs/{run.id}").status_code == 200
    assert [p["name"] for p in client.get("/api/products").json()] == ["Gateway", "Sensor"]
    assert client.get(f"/api/products/{second.id}").status_code == 200
    assert client.get("/api/test-runs/stats").json()["total_runs"] == 3
    assert client.get(f"/api/uploads/info/{artifact.id}").status_code == 200
    stations = client.get("/api/runners/status").json()["runners"]
    assert stations[0]["current_run"]["name"] == "gateway-suite"
    assert client.get("/api/groups").status_code == 403


WRITES = [
    ("custom_runs.create", "POST", "/api/test-runs/custom", {"test_paths": ["a.B"]}),
    ("bloom_publish.execute", "POST", "/api/test-runs/{run}/publish-to-bloom", None),
    ("stations.manage", "POST", "/api/runners/api-keys", {"name": "k"}),
    ("stations.manage", "GET", "/api/runners/api-keys", None),
    ("stations.manage", "PATCH", "/api/runners/bench-1", {"is_active": True}),
    ("products.manage", "POST", "/api/products", {"name": "New"}),
    ("settings.view", "GET", "/api/settings", None),
    ("settings.edit", "PUT", "/api/settings/x", {"value": "y"}),
    ("settings.view", "GET", "/api/settings/notifications/channels", None),
    ("settings.edit", "DELETE", "/api/company-logo/logo", None),
    ("audit.view", "GET", "/api/audit", None),
    ("access.manage", "GET", "/api/groups", None),
    ("access.manage", "GET", "/api/access-requests", None),
    ("admin", "GET", "/api/users", None),
    ("reports.export", "GET", "/api/reports/test-runs/{run}.pdf", None),
    ("settings.view", "GET", "/api/settings/integrations/PLM", None),
    ("settings.edit", "POST", "/api/settings/integrations/PLM", {}),
    ("settings.edit", "POST", "/api/settings/notifications/channels/999/test", None),
    ("settings.edit", "PUT", "/api/company-logo/logo", None),
    ("access.manage", "POST", "/api/access-requests/999/decision", {"decision": "refused"}),
    ("admin", "POST", "/api/users/{viewer}/email/approve", None),
    ("stations.manage", "DELETE", "/api/runners/api-keys/999", None),
    ("admin", "DELETE", "/api/uploads/{artifact}", None),
    ("admin", "DELETE", "/api/test-runs/{run}", None),
    ("products.manage", "DELETE", "/api/products/{product}", None),
    ("stations.manage", "DELETE", "/api/runners/bench-1", None),
]

ALLOWED = {
    "viewer": {"reports.export"},
    "developer": {"reports.export", "custom_runs.create", "bloom_publish.execute"},
    "station_manager": {
        "reports.export",
        "custom_runs.create",
        "bloom_publish.execute",
        "stations.manage",
    },
    "admin": {name for name, *_ in WRITES},
}


@pytest.mark.asyncio
@pytest.mark.parametrize("who", list(ALLOWED))
async def test_route_map_per_base_role_and_group(client, db_session, who):
    first, _, viewer, developer, runs, artifact = await _seed(db_session)
    if who == "station_manager":
        _give(client, "Station Managers", developer)
    actor = {"viewer": viewer, "developer": developer, "station_manager": developer, "admin": ADMIN}[
        who
    ]
    _as(actor)
    for permission, method, path, body in WRITES:
        url = path.format(run=runs[1].id, artifact=artifact.id, product=first.id, viewer=viewer.id)
        response = client.request(method, url, json=body)
        if permission in ALLOWED[who]:
            assert response.status_code != 403, (who, method, path, response.text)
        else:
            assert response.status_code == 403, (who, method, path, response.text)


@pytest.fixture
def sent_mail(monkeypatch):
    sent = []
    monkeypatch.setattr(
        access_requests_api, "send_access_request_email", lambda **kwargs: sent.append(kwargs)
    )
    return sent


@pytest.mark.asyncio
async def test_publish_to_bloom_is_requested_and_granted_with_a_group(client, db_session, sent_mail):
    _, _, viewer, developer, runs, _ = await _seed(db_session)
    _give(client, "Access Managers", developer)

    _as(viewer)
    request = client.post(
        "/api/access-requests",
        json={"resource_type": "publish-to-bloom", "resource_ref": str(runs[1].id)},
    )
    assert request.status_code == 201, request.text
    assert sorted(mail["to_email"] for mail in sent_mail) == ["admin@example.com", "dev@example.com"]
    assert client.get("/api/access-requests").status_code == 403

    _as(developer)
    pending = client.get("/api/access-requests").json()
    assert [row["requester_email"] for row in pending] == ["viewer@example.com"]
    request_id = pending[0]["id"]
    decision = f"/api/access-requests/{request_id}/decision"
    assert client.post(decision, json={"decision": "granted"}).status_code == 422
    readers = _group_id(client, "Results Viewers")
    assert client.post(decision, json={"decision": "granted", "group_id": readers}).status_code == 422
    operators = _group_id(client, "Test Operators")
    granted = client.post(decision, json={"decision": "granted", "group_id": operators})
    assert granted.status_code == 200, granted.text
    assert granted.json()["status"] == "granted"
    assert client.post(decision, json={"decision": "refused"}).status_code == 409

    _as(viewer)
    assert "bloom_publish.execute" in client.get("/api/auth/me").json()["permissions"]


@pytest.mark.asyncio
async def test_admins_are_told_of_requests_too(client, db_session, sent_mail):
    _, _, viewer, _, runs, _ = await _seed(db_session)
    db_session.add(_user("boss@example.com", "Bo Boss", UserRole.admin))
    await db_session.commit()
    _as(viewer)
    client.post(
        "/api/access-requests",
        json={"resource_type": "publish-to-bloom", "resource_ref": str(runs[0].id)},
    )
    assert sorted(mail["to_email"] for mail in sent_mail) == ["admin@example.com", "boss@example.com"]


@pytest.mark.asyncio
async def test_seeding_keeps_existing_rows(db_session):
    from sqlalchemy import func, select

    from app.core.access import seed_default_access

    await seed_default_access(db_session)
    await seed_default_access(db_session)
    assert await db_session.scalar(select(func.count()).select_from(AccessGroup)) == 5
    assert await db_session.scalar(select(func.count()).select_from(Policy)) == 8


@pytest.mark.asyncio
async def test_a_custom_policy_grants_what_only_admins_held(client, db_session):
    _, _, _, developer, _, _ = await _seed(db_session)
    policy = client.post(
        "/api/policies",
        json={
            "name": "Back office",
            "permissions": {"products": ["manage"], "settings": ["view", "edit"], "audit": ["view"]},
        },
    ).json()
    group = client.post("/api/groups", json={"name": "Back office", "policy_ids": [policy["id"]]}).json()

    _as(developer)
    assert client.post("/api/products", json={"name": "Probe"}).status_code == 403
    assert client.get("/api/audit").status_code == 403

    _as(ADMIN)
    assert client.post(f"/api/groups/{group['id']}/members", json={"user_id": developer.id}).status_code == 201

    _as(developer)
    assert client.post("/api/products", json={"name": "Probe"}).status_code == 201
    assert client.get("/api/settings").status_code == 200
    assert client.put("/api/settings/x", json={"value": "y"}).status_code != 403
    assert client.get("/api/audit").status_code == 200
    assert client.get("/api/users").status_code == 403
    assert client.get("/api/groups").status_code == 403


@pytest.mark.asyncio
async def test_seed_renames_administration_and_keeps_its_identity_and_members(db_session):
    from sqlalchemy import select
    from app.core.access import seed_default_access

    await seed_default_access(db_session)
    group = await db_session.scalar(select(AccessGroup).where(AccessGroup.system_key == "app_administration"))
    group.name = "App Administration"
    user = User(email="rename@example.com", full_name="Existing member", role=UserRole.developer, hashed_password="unused", is_active=True)
    db_session.add(user)
    await db_session.flush()
    group_id, user_id = group.id, user.id
    db_session.add(AccessGroupMember(group_id=group_id, user_id=user_id))
    await db_session.flush()
    await seed_default_access(db_session)
    await seed_default_access(db_session)
    assert group.id == group_id
    assert group.name == "Application Administrators"
    assert group.system_key == "app_administration"
    assert await db_session.get(AccessGroupMember, {"group_id": group_id, "user_id": user_id}) is not None
    assert user.role == UserRole.developer


@pytest.mark.asyncio
async def test_access_rosters_return_the_account_picture(client, db_session):
    _, _, _, developer, _, _ = await _seed(db_session)
    developer.profile_picture = b"stored-profile-image"
    await db_session.commit()
    _as(ADMIN)
    group = _give(client, "Test Operators", developer).json()
    member = next(item for item in group["members"] if item["user_id"] == developer.id)
    person = next(item for item in client.get("/api/access/users").json() if item["id"] == developer.id)
    assert member["profile_picture_url"] == developer.profile_picture_url
    assert person["profile_picture_url"] == developer.profile_picture_url
