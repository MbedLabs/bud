"""Holding several groups never widens what the groups allow: management and giving stay guarded.

Every request signs in with a real token; the people hold their groups through stored
memberships.
"""

from sqlalchemy import func, select

from app.core.security import get_password_hash
from app.models.access import AccessGroup, AccessGroupMember, Policy
from app.models.user import User, UserRole

PASSWORD = "Correct-Horse-Battery-9"
ADMIN_ONLY = "Only an Admin gives Application Administrators"


async def _user(db_session, email, role):
    """Save an active user and return its id."""
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


async def _group(db_session, name, *policy_keys):
    """The id of the group with this name, created from the shipped policies when custom."""
    existing = (
        await db_session.execute(select(AccessGroup).where(AccessGroup.name == name))
    ).scalar_one_or_none()
    if existing is not None:
        return existing.id
    policies = [
        (await db_session.execute(select(Policy).where(Policy.system_key == key))).scalar_one()
        for key in policy_keys
    ]
    group = AccessGroup(name=name, policies=policies)
    db_session.add(group)
    await db_session.commit()
    return group.id


async def _hold(db_session, user_id, *group_ids):
    """Give the user each group by storing the memberships."""
    for group_id in group_ids:
        db_session.add(AccessGroupMember(group_id=group_id, user_id=user_id))
    await db_session.commit()


async def _rows(db_session, user_id):
    """How many membership rows the user has."""
    db_session.expire_all()
    return await db_session.scalar(
        select(func.count())
        .select_from(AccessGroupMember)
        .where(AccessGroupMember.user_id == user_id)
    )


def _login(client, email):
    """Sign in and return the bearer header."""
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_many_groups_without_access_management_open_nothing(
    unauthenticated_client, db_session
):
    """Several groups none of which holds access management leave every access route closed."""
    client = unauthenticated_client
    viewer_id = await _user(db_session, "member@example.com", UserRole.viewer)
    target_id = await _user(db_session, "target@example.com", UserRole.viewer)
    groups = [
        await _group(db_session, "Test Operators"),
        await _group(db_session, "Results Viewers"),
        await _group(db_session, "Catalogue", "products"),
        await _group(db_session, "Configuration", "settings"),
        await _group(db_session, "Auditors", "audit"),
    ]
    await _hold(db_session, viewer_id, *groups)
    headers = _login(client, "member@example.com")

    assert client.get("/api/groups", headers=headers).status_code == 403
    assert client.get("/api/access/users", headers=headers).status_code == 403
    given = client.post(
        f"/api/groups/{groups[1]}/members", json={"user_id": target_id}, headers=headers
    )
    assert given.status_code == 403
    assert await _rows(db_session, target_id) == 0


async def test_every_policy_through_several_groups_still_cannot_give_application_administrators(
    unauthenticated_client, db_session
):
    """A non-admin holding access management and every policy across groups is refused."""
    client = unauthenticated_client
    giver_id = await _user(db_session, "giver@example.com", UserRole.developer)
    holder_id = await _user(db_session, "holder@example.com", UserRole.developer)
    recipient_id = await _user(db_session, "recipient@example.com", UserRole.developer)
    admin_group = await _group(db_session, "Application Administrators")
    await _hold(
        db_session,
        giver_id,
        await _group(db_session, "Access Managers"),
        await _group(db_session, "Catalogue", "products"),
        await _group(db_session, "Configuration", "settings"),
        await _group(db_session, "Auditors", "audit"),
        await _group(db_session, "Test Operators"),
    )
    await _hold(db_session, holder_id, admin_group)
    headers = _login(client, "giver@example.com")

    given = client.post(
        f"/api/groups/{admin_group}/members", json={"user_id": recipient_id}, headers=headers
    )
    removed = client.delete(f"/api/groups/{admin_group}/members/{holder_id}", headers=headers)

    assert (given.status_code, given.json()["detail"]) == (403, ADMIN_ONLY)
    assert (removed.status_code, removed.json()["detail"]) == (403, ADMIN_ONLY)
    assert await _rows(db_session, recipient_id) == 0
    assert await _rows(db_session, holder_id) == 1


async def test_a_viewer_with_several_groups_is_refused_station_management(
    unauthenticated_client, db_session
):
    """Giving station management to a Viewer with several groups answers 422 and writes no row."""
    client = unauthenticated_client
    await _user(db_session, "boss@example.com", UserRole.admin)
    viewer_id = await _user(db_session, "member@example.com", UserRole.viewer)
    held = [
        await _group(db_session, "Test Operators"),
        await _group(db_session, "Catalogue", "products"),
        await _group(db_session, "Auditors", "audit"),
    ]
    await _hold(db_session, viewer_id, *held)
    headers = _login(client, "boss@example.com")

    for name in ("Station Managers", "Access Managers"):
        group_id = await _group(db_session, name)
        refused = client.post(
            f"/api/groups/{group_id}/members", json={"user_id": viewer_id}, headers=headers
        )
        assert refused.status_code == 422, refused.text

    assert await _rows(db_session, viewer_id) == len(held)


async def test_access_spread_over_two_groups_does_not_cover_a_third_policy(
    unauthenticated_client, db_session
):
    """A giver with products in one group and stations in another gives the group covering both and is refused the group that adds audit."""
    client = unauthenticated_client
    giver_id = await _user(db_session, "giver@example.com", UserRole.developer)
    recipient_id = await _user(db_session, "recipient@example.com", UserRole.developer)
    await _hold(
        db_session,
        giver_id,
        await _group(db_session, "Access Managers"),
        await _group(db_session, "Catalogue", "products"),
    )
    covered = await _group(db_session, "Back desk", "products", "stations")
    wider = await _group(db_session, "Back desk and audit", "products", "stations", "audit")
    headers = _login(client, "giver@example.com")

    refused = client.post(
        f"/api/groups/{wider}/members", json={"user_id": recipient_id}, headers=headers
    )
    given = client.post(
        f"/api/groups/{covered}/members", json={"user_id": recipient_id}, headers=headers
    )

    assert refused.status_code == 403
    assert given.status_code == 201, given.text
    assert await _rows(db_session, recipient_id) == 1
