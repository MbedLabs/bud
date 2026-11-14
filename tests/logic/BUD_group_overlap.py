"""
* @file     ${tests/logic/BUD_group_overlap.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A person holds any number of groups; access is the base allowance united with them all.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests the access services on a fresh app database for each scenario.
"""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api import groups
from app.core import access
from app.core.access import ALL_PERMISSIONS
from app.models.access import AccessGroup, AccessGroupMember, Policy
from app.models.user import User, UserRole
from tests.logic.group_overlap import GroupOverlapBase


async def add_user(db, email, role, password_hash):
    """Store a user with the given base role."""
    user = User(
        email=email,
        full_name=email.split("@")[0],
        hashed_password=password_hash,
        role=role,
        is_active=True,
        session_version=1,
    )
    db.add(user)
    await db.flush()
    return user


async def shipped_group(db, name):
    """The group of that name with its policies loaded."""
    query = (
        select(AccessGroup)
        .where(AccessGroup.name == name)
        .options(selectinload(AccessGroup.policies))
    )
    return (await db.execute(query)).scalar_one()


async def custom_group(db, name, *policy_keys):
    """A new group bundling the shipped policies with these keys."""
    policies = [
        (await db.execute(select(Policy).where(Policy.system_key == key))).scalar_one()
        for key in policy_keys
    ]
    group = AccessGroup(name=name, policies=policies)
    db.add(group)
    await db.flush()
    return group


async def hold(db, user, *held):
    """Give the user each group by storing the membership rows."""
    for group in held:
        db.add(AccessGroupMember(group_id=group.id, user_id=user.id))
    await db.flush()


async def release(db, user, group):
    """Remove one membership row of the user."""
    membership = await db.get(AccessGroupMember, {"group_id": group.id, "user_id": user.id})
    await db.delete(membership)
    await db.flush()


async def memberships(db, user):
    """How many membership rows the user has."""
    query = (
        select(func.count())
        .select_from(AccessGroupMember)
        .where(AccessGroupMember.user_id == user.id)
    )
    return await db.scalar(query)


async def outcome(check):
    """None when the check passes, else the HTTPException it raises."""
    try:
        return await check
    except HTTPException as error:
        return error


class GroupOverlapTest(GroupOverlapBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_all_permissions = ALL_PERMISSIONS
        self.tc_union = self.scenario(self.union)
        self.tc_release = self.scenario(self.release_groups)
        self.tc_admin = {
            count: self.scenario(lambda db, count=count: self.admin(db, count))
            for count in self.parameters.GROUP_ADMIN_MEMBERSHIPS
        }
        self.tc_listed = self.scenario(self.listed)
        self.tc_station_check = self.scenario(self.station_check)
        self.tc_giver = self.scenario(self.giver)
        self.tc_twice = self.scenario(self.twice)

    def scenario(self, run):
        """Run one scenario on a fresh app database session."""
        self.bud.bud_start_app()
        return self.bud.bud_await(run(self.bud.bud_open_session(on_app=True)))

    async def union(self, db):
        """A developer holding two groups, and two developers holding one each."""
        p = self.parameters
        stations = await shipped_group(db, p.GROUP_STATIONS)
        access_managers = await shipped_group(db, p.GROUP_ACCESS)
        both = await add_user(db, "both@example.com", UserRole.developer, p.GROUP_PASSWORD_HASH)
        only_stations = await add_user(
            db, "stations@example.com", UserRole.developer, p.GROUP_PASSWORD_HASH
        )
        only_access = await add_user(
            db, "access@example.com", UserRole.developer, p.GROUP_PASSWORD_HASH
        )
        await hold(db, both, stations, access_managers)
        await hold(db, only_stations, stations)
        await hold(db, only_access, access_managers)
        base = access.base_role_permissions(UserRole.developer)
        return {
            "both": await access.effective_permissions(db, both),
            "base and groups": access.app_scoped(
                base | access.group_permissions(stations) | access.group_permissions(access_managers)
            ),
            "each holder": await access.effective_permissions(db, only_stations)
            | await access.effective_permissions(db, only_access),
            "managed in base": p.GROUP_MANAGED & base,
        }

    async def release_groups(self, db):
        """Release groups that carry the same permission one at a time."""
        p = self.parameters
        stations = await shipped_group(db, p.GROUP_STATIONS)
        access_managers = await shipped_group(db, p.GROUP_ACCESS)
        developer = await add_user(db, "dev@example.com", UserRole.developer, p.GROUP_PASSWORD_HASH)
        await hold(db, developer, stations, access_managers)
        await release(db, developer, stations)
        found = {"one left": await access.effective_permissions(db, developer)}
        await release(db, developer, access_managers)
        found["none left"] = await access.effective_permissions(db, developer)
        found["developer base"] = access.app_scoped(access.base_role_permissions(UserRole.developer))
        north = await custom_group(db, "Auditors north", "audit")
        south = await custom_group(db, "Auditors south", "audit")
        viewer = await add_user(db, "viewer@example.com", UserRole.viewer, p.GROUP_PASSWORD_HASH)
        await hold(db, viewer, north, south)
        found["audit both"] = await access.effective_permissions(db, viewer)
        await release(db, viewer, north)
        found["audit one"] = await access.effective_permissions(db, viewer)
        await release(db, viewer, south)
        found["audit none"] = await access.effective_permissions(db, viewer)
        found["viewer base"] = access.app_scoped(access.base_role_permissions(UserRole.viewer))
        return found

    async def admin(self, db, count):
        """An administrator holding the given number of groups."""
        p = self.parameters
        admin = await add_user(
            db, f"admin{count}@example.com", UserRole.admin, p.GROUP_PASSWORD_HASH
        )
        for name in p.GROUP_ADMIN_GROUPS[:count]:
            await hold(db, admin, await shipped_group(db, name))
        return await memberships(db, admin), await access.effective_permissions(db, admin)

    async def listed(self, db):
        """The groups of three users, one of them holding none."""
        p = self.parameters
        owner = await add_user(db, "owner@example.com", UserRole.developer, p.GROUP_PASSWORD_HASH)
        other = await add_user(db, "other@example.com", UserRole.developer, p.GROUP_PASSWORD_HASH)
        bystander = await add_user(
            db, "bystander@example.com", UserRole.viewer, p.GROUP_PASSWORD_HASH
        )
        for name in p.GROUP_OWNER_GROUPS:
            await hold(db, owner, await shipped_group(db, name))
        await hold(db, other, await shipped_group(db, p.GROUP_STATIONS))
        return {
            name: [group.name for group in await access.user_groups(db, user.id)]
            for name, user in (("owner", owner), ("other", other), ("bystander", bystander))
        }

    async def station_check(self, db):
        """Give the station group to a viewer and a developer who hold the same other groups."""
        p = self.parameters
        admin = User(email=p.GROUP_GIVER_EMAIL, full_name=p.GROUP_GIVER_NAME, role=UserRole.admin)
        lab = await custom_group(db, "Lab", "results", "custom_runs")
        readers = await shipped_group(db, p.GROUP_READERS)
        stations = await shipped_group(db, p.GROUP_STATIONS)
        viewer = await add_user(db, "viewer@example.com", UserRole.viewer, p.GROUP_PASSWORD_HASH)
        developer = await add_user(db, "dev@example.com", UserRole.developer, p.GROUP_PASSWORD_HASH)
        await hold(db, viewer, readers, lab)
        await hold(db, developer, readers, lab)
        return {
            "viewer": await outcome(groups.check_giveable(db, admin, stations, viewer)),
            "developer": await outcome(groups.check_giveable(db, admin, stations, developer)),
        }

    async def giver(self, db):
        """A developer giver whose access is spread over two groups."""
        p = self.parameters
        products = await custom_group(db, "Products crew", "products")
        stations = await custom_group(db, "Stations crew", "stations")
        giver = await add_user(db, "giver@example.com", UserRole.developer, p.GROUP_PASSWORD_HASH)
        recipient = await add_user(
            db, "recipient@example.com", UserRole.developer, p.GROUP_PASSWORD_HASH
        )
        await hold(db, giver, products, stations)
        both = await custom_group(db, "Back desk", "products", "stations")
        wider = await custom_group(db, "Back office", "products", "settings")
        return {
            "covered": await outcome(groups.check_giveable(db, giver, both, recipient)),
            "wider": await outcome(groups.check_giveable(db, giver, wider, recipient)),
        }

    async def twice(self, db):
        """Give the same group to the same viewer twice."""
        p = self.parameters
        admin = User(email=p.GROUP_GIVER_EMAIL, full_name=p.GROUP_GIVER_NAME, role=UserRole.admin)
        operators = await shipped_group(db, p.GROUP_OPERATORS)
        viewer = await add_user(db, "viewer@example.com", UserRole.viewer, p.GROUP_PASSWORD_HASH)
        first = await groups.give_group(db, admin, operators, viewer)
        second = await groups.give_group(db, admin, operators, viewer)
        return {"first": first, "second": second, "memberships": await memberships(db, viewer)}

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    GroupOverlapTest().run()
