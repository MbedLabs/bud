"""
* @file     ${tests/logic/application_policies.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests app-level access over several application policies.
* @author   Amine El Omari
* @date     2026-11-18
* @version  1.0.0
* @note     Base class containing the bud methods of permission evaluation and giving rules; each step opens its own app.
"""

from budtestlibrary import parameterized
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

import tests.parameters as params
from app.api import groups
from app.core import access
from app.core.access import ALL_PERMISSIONS
from app.models.access import AccessGroup, Policy, user_application_policies
from app.models.user import User, UserRole
from tests.bud_test_base import BudAppTestCase


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


async def shipped_policy(db, key):
    """The shipped policy with this system key."""
    return (await db.execute(select(Policy).where(Policy.system_key == key))).scalar_one()


async def custom_policy(db, name, permissions):
    """A new policy with these permissions."""
    policy = Policy(name=name, permissions=permissions)
    db.add(policy)
    await db.flush()
    return policy


async def custom_group(db, name, *policies):
    """A new group bundling these policies, with them loaded."""
    group = AccessGroup(name=name, policies=list(policies))
    db.add(group)
    await db.flush()
    query = (
        select(AccessGroup)
        .where(AccessGroup.id == group.id)
        .options(selectinload(AccessGroup.policies))
    )
    return (await db.execute(query)).scalar_one()


async def hold(db, user, *policies):
    """Store each policy as one of the user's application policies."""
    for policy in policies:
        await db.execute(
            user_application_policies.insert().values(user_id=user.id, policy_id=policy.id)
        )
    await db.flush()


async def release(db, user, policy):
    """Remove one application policy of the user."""
    await db.execute(
        user_application_policies.delete().where(
            user_application_policies.c.user_id == user.id,
            user_application_policies.c.policy_id == policy.id,
        )
    )
    await db.flush()


async def outcome(check):
    """None when the check passes, else the HTTPException it raises."""
    try:
        return await check
    except HTTPException as error:
        return error


class ApplicationPoliciesBase(BudAppTestCase):

    def run_on_app(self, scenario):
        """Run one scenario on a fresh app database session."""
        self.bud.bud_start_app()
        return self.bud.bud_await(scenario(self.bud.bud_open_session(on_app=True)))

    def bud_two_application_policies_give_their_union(self):
        p = self.parameters

        async def scenario(db):
            stations = await shipped_policy(db, p.LAP_STATIONS)
            access_management = await shipped_policy(db, p.LAP_ACCESS)
            both = await add_user(db, "both@example.com", UserRole.developer, p.LAP_PASSWORD_HASH)
            only_stations = await add_user(
                db, "stations@example.com", UserRole.developer, p.LAP_PASSWORD_HASH
            )
            only_access = await add_user(
                db, "access@example.com", UserRole.developer, p.LAP_PASSWORD_HASH
            )
            await hold(db, both, stations, access_management)
            await hold(db, only_stations, stations)
            await hold(db, only_access, access_management)
            base = access.base_role_permissions(UserRole.developer)
            return {
                "both": await access.effective_permissions(db, both),
                "base and policies": access.app_scoped(
                    base
                    | access.permission_set(stations.permissions)
                    | access.permission_set(access_management.permissions)
                ),
                "each holder": await access.effective_permissions(db, only_stations)
                | await access.effective_permissions(db, only_access),
                "managed in base": p.LAP_MANAGED & base,
            }

        found = self.run_on_app(scenario)
        self.print_variables({"both": sorted(found["both"])})
        self.assertEqual(found["both"], found["base and policies"], msg=p.MSG_LAP_UNION)
        self.assertEqual(found["both"], found["each holder"], msg=p.MSG_LAP_UNION_OF_EACH)
        self.assertEqual(p.LAP_MANAGED <= found["both"], True, msg=p.MSG_LAP_MANAGED)
        self.assertEqual(found["managed in base"], set(), msg=p.MSG_LAP_NOT_BASE)

    def bud_a_shared_permission_stays_until_both_policies_go(self):
        p = self.parameters

        async def scenario(db):
            north = await custom_policy(db, "Auditors north", p.LAP_AUDIT_PERMISSIONS)
            south = await custom_policy(db, "Auditors south", p.LAP_AUDIT_PERMISSIONS)
            viewer = await add_user(db, "viewer@example.com", UserRole.viewer, p.LAP_PASSWORD_HASH)
            await hold(db, viewer, north, south)
            found = {"both": await access.effective_permissions(db, viewer)}
            await release(db, viewer, north)
            found["one"] = await access.effective_permissions(db, viewer)
            await release(db, viewer, south)
            found["none"] = await access.effective_permissions(db, viewer)
            found["viewer base"] = access.app_scoped(access.base_role_permissions(UserRole.viewer))
            return found

        found = self.run_on_app(scenario)
        self.print_variables({key: sorted(value) for key, value in found.items()})
        self.assertIn(p.LAP_AUDIT_VIEW, found["both"], msg=p.MSG_LAP_KEPT)
        self.assertIn(p.LAP_AUDIT_VIEW, found["one"], msg=p.MSG_LAP_KEPT)
        self.assertEqual(found["none"], found["viewer base"], msg=p.MSG_LAP_DROPPED)

    @parameterized(params.LAP_ADMIN_COUNTS)
    def bud_admin_holds_every_permission(self, count):
        p = self.parameters

        async def scenario(db):
            admin = await add_user(
                db, f"admin{count}@example.com", UserRole.admin, p.LAP_PASSWORD_HASH
            )
            for key in p.LAP_ADMIN_POLICIES[:count]:
                await hold(db, admin, await shipped_policy(db, key))
            return (
                len(await access.application_policies(db, admin.id)),
                await access.effective_permissions(db, admin),
            )

        held, permissions = self.run_on_app(scenario)
        self.assertEqual(held, count, msg=p.MSG_LAP_ADMIN_COUNT)
        self.assertEqual(permissions, ALL_PERMISSIONS, msg=p.MSG_LAP_ADMIN_ALL)

    def bud_application_policies_lists_one_users_policies_by_name(self):
        p = self.parameters

        async def scenario(db):
            owner = await add_user(db, "owner@example.com", UserRole.developer, p.LAP_PASSWORD_HASH)
            other = await add_user(db, "other@example.com", UserRole.developer, p.LAP_PASSWORD_HASH)
            bystander = await add_user(
                db, "bystander@example.com", UserRole.viewer, p.LAP_PASSWORD_HASH
            )
            for key in p.LAP_OWNER_POLICIES:
                await hold(db, owner, await shipped_policy(db, key))
            await hold(db, other, await shipped_policy(db, p.LAP_STATIONS))
            return {
                name: [policy.name for policy in await access.application_policies(db, user.id)]
                for name, user in (("owner", owner), ("other", other), ("bystander", bystander))
            }

        found = self.run_on_app(scenario)
        self.print_variables(found)
        self.assertEqual(found["owner"], p.LAP_OWNER_NAMES, msg=p.MSG_LAP_LISTED)
        self.assertEqual(found["other"], [p.LAP_STATIONS_NAME], msg=p.MSG_LAP_LISTED)
        self.assertEqual(found["bystander"], [], msg=p.MSG_LAP_LISTED)

    def bud_station_management_is_checked_per_given_group(self):
        p = self.parameters

        async def scenario(db):
            admin = User(email=p.LAP_GIVER_EMAIL, full_name=p.LAP_GIVER_NAME, role=UserRole.admin)
            stations = await custom_group(
                db, "Station crew", await shipped_policy(db, p.LAP_STATIONS)
            )
            viewer = await add_user(db, "viewer@example.com", UserRole.viewer, p.LAP_PASSWORD_HASH)
            developer = await add_user(
                db, "dev@example.com", UserRole.developer, p.LAP_PASSWORD_HASH
            )
            return {
                "viewer": await outcome(groups.check_giveable(db, admin, stations, viewer)),
                "developer": await outcome(groups.check_giveable(db, admin, stations, developer)),
            }

        found = self.run_on_app(scenario)
        self.print_variables({key: type(value).__name__ for key, value in found.items()})
        self.assertEqual(
            type(found["viewer"]).__name__, p.HTTP_EXCEPTION, msg=p.MSG_LAP_VIEWER_REFUSED
        )
        self.assertEqual(
            getattr(found["viewer"], "status_code", None),
            p.STATUS_UNPROCESSABLE,
            msg=p.MSG_LAP_VIEWER_CODE,
        )
        self.assertEqual(
            type(found["developer"]).__name__, p.NONE_TYPE, msg=p.MSG_LAP_DEVELOPER_ACCEPTED
        )

    def bud_giver_is_judged_on_all_their_application_policies(self):
        p = self.parameters

        async def scenario(db):
            products = await shipped_policy(db, p.LAP_PRODUCTS)
            stations = await shipped_policy(db, p.LAP_STATIONS)
            settings = await shipped_policy(db, p.LAP_SETTINGS)
            giver = await add_user(db, "giver@example.com", UserRole.developer, p.LAP_PASSWORD_HASH)
            recipient = await add_user(
                db, "recipient@example.com", UserRole.developer, p.LAP_PASSWORD_HASH
            )
            await hold(db, giver, products, stations)
            both = await custom_group(db, "Back desk", products, stations)
            wider = await custom_group(db, "Back office", products, settings)
            return {
                "covered": await outcome(groups.check_giveable(db, giver, both, recipient)),
                "wider": await outcome(groups.check_giveable(db, giver, wider, recipient)),
            }

        found = self.run_on_app(scenario)
        self.print_variables({key: type(value).__name__ for key, value in found.items()})
        self.assertEqual(type(found["covered"]).__name__, p.NONE_TYPE, msg=p.MSG_LAP_GIVER_COVERED)
        self.assertEqual(
            type(found["wider"]).__name__, p.HTTP_EXCEPTION, msg=p.MSG_LAP_GIVER_REFUSED
        )
        self.assertEqual(
            getattr(found["wider"], "status_code", None),
            p.STATUS_FORBIDDEN,
            msg=p.MSG_LAP_GIVER_CODE,
        )
