"""A person holds any number of groups: evaluation and giving rules over overlapping groups.

Access is the base role's allowance united with the policies of every held group; giving a
group never replaces another membership, and the recipient and giver rules apply to each group
when it is given.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.groups import check_giveable, give_group
from app.core.access import (
    ALL_PERMISSIONS,
    base_role_permissions,
    effective_permissions,
    group_permissions,
    user_groups,
)
from app.models.access import AccessGroup, AccessGroupMember, Policy
from app.models.user import User, UserRole


async def _user(db, email, role):
    """Persist a user with the given base role."""
    user = User(
        email=email,
        full_name=email.split("@")[0],
        hashed_password="x",
        role=role,
        is_active=True,
        session_version=1,
    )
    db.add(user)
    await db.flush()
    return user


async def _group(db, name):
    """The shipped or custom group with this name, with its policies loaded."""
    return (
        await db.execute(
            select(AccessGroup)
            .where(AccessGroup.name == name)
            .options(selectinload(AccessGroup.policies))
        )
    ).scalar_one()


async def _custom_group(db, name, *policy_keys):
    """Create a custom group bundling the shipped policies with these keys."""
    policies = [
        (await db.execute(select(Policy).where(Policy.system_key == key))).scalar_one()
        for key in policy_keys
    ]
    group = AccessGroup(name=name, policies=policies)
    db.add(group)
    await db.flush()
    return group


async def _hold(db, user, *groups):
    """Give the user each group by inserting the membership rows directly."""
    for group in groups:
        db.add(AccessGroupMember(group_id=group.id, user_id=user.id))
    await db.flush()


async def _release(db, user, group):
    """Remove one membership row of the user."""
    membership = await db.get(AccessGroupMember, {"group_id": group.id, "user_id": user.id})
    await db.delete(membership)
    await db.flush()


async def _count(db, user):
    """How many membership rows the user has."""
    return await db.scalar(
        select(func.count())
        .select_from(AccessGroupMember)
        .where(AccessGroupMember.user_id == user.id)
    )


async def test_a_developer_with_two_groups_holds_the_union_of_both(db_session):
    """The base allowance united with two groups equals the union of each group on its own."""
    stations = await _group(db_session, "Station Managers")
    access = await _group(db_session, "Access Managers")
    both = await _user(db_session, "both@example.com", UserRole.developer)
    only_stations = await _user(db_session, "stations@example.com", UserRole.developer)
    only_access = await _user(db_session, "access@example.com", UserRole.developer)
    await _hold(db_session, both, stations, access)
    await _hold(db_session, only_stations, stations)
    await _hold(db_session, only_access, access)

    combined = await effective_permissions(db_session, both)

    assert combined == (
        base_role_permissions(UserRole.developer)
        | group_permissions(stations)
        | group_permissions(access)
    )
    assert combined == (
        await effective_permissions(db_session, only_stations)
        | await effective_permissions(db_session, only_access)
    )
    assert {"stations.manage", "access.manage"} <= combined
    assert not {"stations.manage", "access.manage"} & base_role_permissions(UserRole.developer)


async def test_a_permission_two_groups_carry_stays_until_both_are_gone(db_session):
    """Removing one of two groups that carry a permission keeps it; removing both drops it."""
    stations = await _group(db_session, "Station Managers")
    access = await _group(db_session, "Access Managers")
    developer = await _user(db_session, "dev@example.com", UserRole.developer)
    await _hold(db_session, developer, stations, access)

    await _release(db_session, developer, stations)
    held = await effective_permissions(db_session, developer)
    assert {"stations.manage", "access.manage"} <= held

    await _release(db_session, developer, access)
    assert await effective_permissions(db_session, developer) == base_role_permissions(
        UserRole.developer
    )

    first = await _custom_group(db_session, "Auditors north", "audit")
    second = await _custom_group(db_session, "Auditors south", "audit")
    viewer = await _user(db_session, "viewer@example.com", UserRole.viewer)
    await _hold(db_session, viewer, first, second)
    assert "audit.view" in await effective_permissions(db_session, viewer)
    await _release(db_session, viewer, first)
    assert "audit.view" in await effective_permissions(db_session, viewer)
    await _release(db_session, viewer, second)
    assert await effective_permissions(db_session, viewer) == base_role_permissions(UserRole.viewer)


@pytest.mark.parametrize("memberships", [0, 1, 3])
async def test_an_admin_holds_every_permission_with_any_number_of_groups(db_session, memberships):
    """The Admin base role holds every permission whatever groups are held."""
    admin = await _user(db_session, f"admin{memberships}@example.com", UserRole.admin)
    names = ["Results Viewers", "Test Operators", "Station Managers"][:memberships]
    for name in names:
        await _hold(db_session, admin, await _group(db_session, name))

    assert await _count(db_session, admin) == memberships
    assert await effective_permissions(db_session, admin) == ALL_PERMISSIONS


async def test_user_groups_lists_all_of_one_users_groups_by_name(db_session):
    """Every group of the user, ordered by name, and none of another user's."""
    names = ["Test Operators", "Access Managers", "Results Viewers"]
    owner = await _user(db_session, "owner@example.com", UserRole.developer)
    other = await _user(db_session, "other@example.com", UserRole.developer)
    bystander = await _user(db_session, "bystander@example.com", UserRole.viewer)
    for name in names:
        await _hold(db_session, owner, await _group(db_session, name))
    await _hold(db_session, other, await _group(db_session, "Station Managers"))

    assert [group.name for group in await user_groups(db_session, owner.id)] == sorted(names)
    assert [group.name for group in await user_groups(db_session, other.id)] == ["Station Managers"]
    assert await user_groups(db_session, bystander.id) == []


async def test_station_management_is_checked_for_each_group_when_it_is_given(db_session):
    """A Viewer with other groups is refused a station group; a Developer with them is accepted."""
    admin = User(email="boss@example.com", full_name="Boss", role=UserRole.admin)
    lab = await _custom_group(db_session, "Lab", "results", "custom_runs")
    readers = await _group(db_session, "Results Viewers")
    stations = await _group(db_session, "Station Managers")
    viewer = await _user(db_session, "viewer@example.com", UserRole.viewer)
    developer = await _user(db_session, "dev@example.com", UserRole.developer)
    await _hold(db_session, viewer, readers, lab)
    await _hold(db_session, developer, readers, lab)

    with pytest.raises(HTTPException) as refused:
        await check_giveable(db_session, admin, stations, viewer)
    assert refused.value.status_code == 422
    assert await check_giveable(db_session, admin, stations, developer) is None


async def test_a_giver_is_judged_on_the_access_of_all_their_groups(db_session):
    """A Developer giver whose access is spread over two groups gives only what both cover."""
    products = await _custom_group(db_session, "Products crew", "products")
    stations = await _custom_group(db_session, "Stations crew", "stations")
    giver = await _user(db_session, "giver@example.com", UserRole.developer)
    recipient = await _user(db_session, "recipient@example.com", UserRole.developer)
    await _hold(db_session, giver, products, stations)
    both = await _custom_group(db_session, "Back desk", "products", "stations")
    wider = await _custom_group(db_session, "Back office", "products", "settings")

    assert await check_giveable(db_session, giver, both, recipient) is None
    with pytest.raises(HTTPException) as refused:
        await check_giveable(db_session, giver, wider, recipient)
    assert refused.value.status_code == 403


async def test_giving_the_same_group_twice_leaves_one_membership(db_session):
    """The first give adds the row and reports it; the same pair again adds nothing."""
    admin = User(email="boss@example.com", full_name="Boss", role=UserRole.admin)
    operators = await _group(db_session, "Test Operators")
    viewer = await _user(db_session, "viewer@example.com", UserRole.viewer)

    assert await give_group(db_session, admin, operators, viewer) is True
    assert await give_group(db_session, admin, operators, viewer) is False
    assert await _count(db_session, viewer) == 1
