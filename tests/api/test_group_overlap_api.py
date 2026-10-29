"""A person holds any number of groups over HTTP: giving, removing, deleting and requesting.

Access is the base role's allowance united with every held group; giving a group never replaces
another membership, and removing or deleting a group takes away only that group's contribution.
"""

import pytest
from sqlalchemy import func, select

from app.api import access_requests as access_requests_api
from app.api.auth import get_current_active_entity, get_current_user
from app.core.access import base_role_permissions
from app.main import app
from app.models import TestRun as RunModel
from app.models.access import AccessGroupMember
from app.models.audit import AuditEvent
from app.models.user import User, UserRole

DUPLICATE = "The user already has this group"


def _user(email, name, role):
    """An unsaved active user."""
    return User(
        email=email,
        full_name=name,
        hashed_password="x",
        role=role,
        is_active=True,
        session_version=1,
    )


async def _people(db_session):
    """A saved Admin, Developer and Viewer."""
    boss = _user("boss@example.com", "Bo Boss", UserRole.admin)
    developer = _user("dev@example.com", "Dee Developer", UserRole.developer)
    viewer = _user("viewer@example.com", "Val Viewer", UserRole.viewer)
    db_session.add_all([boss, developer, viewer])
    await db_session.commit()
    return boss, developer, viewer


def _as(user):
    """Make the user the signed-in person for the next requests."""

    async def current():
        """The signed-in person."""
        return user

    app.dependency_overrides[get_current_user] = current
    app.dependency_overrides[get_current_active_entity] = current


def _group_id(client, name):
    """The id of the group with this name."""
    return next(g["id"] for g in client.get("/api/groups").json() if g["name"] == name)


def _policy_id(client, name):
    """The id of the policy with this name."""
    return next(p["id"] for p in client.get("/api/policies").json() if p["name"] == name)


def _give(client, group, user):
    """Give the user the group with this name."""
    return client.post(f"/api/groups/{_group_id(client, group)}/members", json={"user_id": user.id})


def _take(client, group, user):
    """Take the group with this name from the user."""
    return client.delete(f"/api/groups/{_group_id(client, group)}/members/{user.id}")


def _custom_group(client, name, *policies):
    """Create a custom group bundling the policies with these names; return its id."""
    created = client.post(
        "/api/groups",
        json={"name": name, "policy_ids": [_policy_id(client, policy) for policy in policies]},
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def _access_user(client, user):
    """The access listing row of the user."""
    return next(row for row in client.get("/api/access/users").json() if row["id"] == user.id)


async def _rows(db_session, user_id):
    """How many membership rows the user with this id has."""
    return await db_session.scalar(
        select(func.count())
        .select_from(AccessGroupMember)
        .where(AccessGroupMember.user_id == user_id)
    )


async def _events(db_session, action):
    """How many audit events with this action exist."""
    return await db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.action == action)
    )


@pytest.fixture
def sent_mail(monkeypatch):
    """Replace the access request mail function with one that records its calls."""
    sent = []
    monkeypatch.setattr(
        access_requests_api, "send_access_request_email", lambda **kwargs: sent.append(kwargs)
    )
    return sent


async def test_two_groups_give_a_person_the_union_of_both(client, db_session):
    """A Developer given two groups is listed in each once and holds the union of their access."""
    boss, developer, viewer = await _people(db_session)
    _as(boss)
    for name in ("Station Managers", "Access Managers"):
        given = _give(client, name, developer)
        assert given.status_code == 201, given.text
        assert [m["user_id"] for m in given.json()["members"]] == [developer.id]

    groups = {g["name"]: g for g in client.get("/api/groups").json()}
    expected = (
        base_role_permissions(UserRole.developer)
        | set(groups["Station Managers"]["permissions"])
        | set(groups["Access Managers"]["permissions"])
    )
    row = _access_user(client, developer)
    assert [g["name"] for g in row["groups"]] == ["Access Managers", "Station Managers"]
    assert set(row["permissions"]) == expected
    assert {"stations.manage", "access.manage"} <= set(row["permissions"])
    assert row["role"] == "developer"

    _as(developer)
    assert set(client.get("/api/auth/me").json()["permissions"]) == expected

    _as(boss)
    for name in ("Results Viewers", "Test Operators"):
        assert _give(client, name, viewer).status_code == 201
    _as(viewer)
    held = set(client.get("/api/auth/me").json()["permissions"])
    assert {"custom_runs.create", "bloom_publish.execute"} <= held


async def test_removing_one_group_keeps_what_the_other_still_gives(client, db_session):
    """Removing a group drops only its own contribution; a shared permission stays."""
    boss, developer, _ = await _people(db_session)
    _as(boss)
    _give(client, "Station Managers", developer)
    _give(client, "Access Managers", developer)

    assert _take(client, "Station Managers", developer).status_code == 200
    row = _access_user(client, developer)
    assert {"stations.manage", "access.manage"} <= set(row["permissions"])
    assert [g["name"] for g in row["groups"]] == ["Access Managers"]

    assert _take(client, "Access Managers", developer).status_code == 200
    row = _access_user(client, developer)
    assert not {"stations.manage", "access.manage"} & set(row["permissions"])
    assert set(row["permissions"]) == base_role_permissions(UserRole.developer)
    assert (row["role"], row["groups"]) == ("developer", [])
    assert _take(client, "Access Managers", developer).status_code == 404


async def test_giving_a_held_group_again_is_refused_without_a_change(client, db_session):
    """The duplicate assignment answers 409 and adds no row and no audit event."""
    boss, _, viewer = await _people(db_session)
    viewer_id = viewer.id
    _as(boss)
    assert _give(client, "Test Operators", viewer).status_code == 201
    rows, events = await _rows(db_session, viewer_id), await _events(db_session, "group.member_added")

    again = _give(client, "Test Operators", viewer)

    assert (again.status_code, again.json()) == (409, {"detail": DUPLICATE})
    db_session.expire_all()
    assert await _rows(db_session, viewer_id) == rows == 1
    assert await _events(db_session, "group.member_added") == events == 1


async def test_a_permission_follows_each_group_that_gives_it(client, db_session):
    """Two disjoint custom groups give a Viewer two routes; removing one closes only its route."""
    boss, _, viewer = await _people(db_session)
    _as(boss)
    catalogue = _custom_group(client, "Catalogue", "Products")
    _custom_group(client, "Configuration", "Settings and integrations")
    assert client.post(f"/api/groups/{catalogue}/members", json={"user_id": viewer.id}).status_code == 201
    assert _give(client, "Configuration", viewer).status_code == 201

    _as(viewer)
    assert client.post("/api/products", json={"name": "Probe"}).status_code != 403
    assert client.put("/api/settings/x", json={"value": "y"}).status_code != 403

    _as(boss)
    assert client.delete(f"/api/groups/{catalogue}/members/{viewer.id}").status_code == 200
    _as(viewer)
    assert client.post("/api/products", json={"name": "Probe two"}).status_code == 403
    assert client.put("/api/settings/x", json={"value": "y"}).status_code != 403

    _as(boss)
    assert _take(client, "Configuration", viewer).status_code == 200
    _as(viewer)
    assert client.put("/api/settings/x", json={"value": "y"}).status_code == 403


async def test_deleting_a_group_keeps_the_other_memberships_and_the_base_role(client, db_session):
    """Deleting one custom group removes only its rows; the person keeps the rest."""
    boss, developer, _ = await _people(db_session)
    developer_id = developer.id
    _as(boss)
    doomed = _custom_group(client, "Short lived", "Products")
    _custom_group(client, "Long lived", "Audit log")
    assert client.post(f"/api/groups/{doomed}/members", json={"user_id": developer.id}).status_code == 201
    assert _give(client, "Long lived", developer).status_code == 201
    assert _give(client, "Test Operators", developer).status_code == 201

    assert client.delete(f"/api/groups/{doomed}").status_code == 204

    row = _access_user(client, developer)
    assert [g["name"] for g in row["groups"]] == ["Long lived", "Test Operators"]
    assert row["role"] == "developer"
    assert "audit.view" in row["permissions"]
    assert "products.manage" not in row["permissions"]
    db_session.expire_all()
    assert await _rows(db_session, developer_id) == 2


async def test_granting_an_access_request_adds_a_group_and_keeps_the_others(
    client, db_session, sent_mail
):
    """A grant adds the chosen group beside the requester's other group; a held group stays one."""
    boss, _, viewer = await _people(db_session)
    viewer_id = viewer.id
    run = RunModel(name="suite", test_case_list="a", status="Completed")
    other = RunModel(name="other suite", test_case_list="a", status="Completed")
    db_session.add_all([run, other])
    await db_session.commit()
    _as(boss)
    assert _give(client, "Results Viewers", viewer).status_code == 201
    operators = _group_id(client, "Test Operators")

    def ask(ref):
        """The viewer asks for Publish to Bloom on this run; return the decision URL."""
        _as(viewer)
        created = client.post(
            "/api/access-requests", json={"resource_type": "publish-to-bloom", "resource_ref": ref}
        )
        assert created.status_code == 201, created.text
        _as(boss)
        return f"/api/access-requests/{created.json()['id']}/decision"

    first, second = ask(str(run.id)), ask(str(other.id))
    granted = client.post(first, json={"decision": "granted", "group_id": operators})
    assert (granted.status_code, granted.json()["status"]) == (200, "granted")
    assert [g["name"] for g in _access_user(client, viewer)["groups"]] == [
        "Results Viewers",
        "Test Operators",
    ]

    again = client.post(second, json={"decision": "granted", "group_id": operators})
    assert (again.status_code, again.json()["status"]) == (200, "granted")
    db_session.expire_all()
    assert await _rows(db_session, viewer_id) == 2
    assert (
        await db_session.get(AccessGroupMember, {"group_id": operators, "user_id": viewer_id})
        is not None
    )
