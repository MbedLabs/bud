"""
* @file     ${tests/api/BUD_group_overlap_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A person holds any number of groups; each group adds and takes away only its own access.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests an administrator, a developer and a viewer on a fresh app per scenario.
"""

from unittest import mock

from app.api import access_requests
from app.core.access import base_role_permissions
from app.models import TestRun
from app.models.access import AccessGroupMember
from app.models.audit import AuditEvent
from app.models.user import User, UserRole
from tests.api.group_overlap_api import GroupOverlapApiBase


class GroupOverlapApiTest(GroupOverlapApiBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_checks = {
            "union": self.union(),
            "removal": self.removal(),
            "duplicate": self.duplicate(),
            "routes": self.routes(),
            "deletion": self.deletion(),
            "request": self.request(),
        }

    def people(self):
        """Start a fresh app with an administrator, a developer and a viewer."""
        self.bud.bud_start_app()
        return [
            self.bud.bud_add_to_app(
                User(
                    email=email,
                    full_name=name,
                    hashed_password="x",
                    role=UserRole(role),
                    is_active=True,
                    session_version=1,
                )
            )
            for email, name, role in self.parameters.OVERLAP_PEOPLE
        ]

    def call(self, method, path, **kwargs):
        """Send one request as the signed-in person."""
        return self.bud.bud_request(method, path, **kwargs)

    def group_id(self, name):
        """The id of the group of that name."""
        return next(
            g["id"]
            for g in self.call(self.parameters.GET, self.parameters.GROUPS_PATH).json()
            if g["name"] == name
        )

    def give(self, group, user):
        """Give the group of that name, or of that id, to the user."""
        p = self.parameters
        group_id = group if isinstance(group, int) else self.group_id(group)
        return self.call(p.POST, p.GROUP_MEMBERS_PATH.format(group_id), json={"user_id": user.id})

    def take(self, group, user):
        """Take the group of that name, or of that id, from the user."""
        p = self.parameters
        group_id = group if isinstance(group, int) else self.group_id(group)
        return self.call(p.DELETE, p.GROUP_MEMBER_PATH.format(group_id, user.id))

    def custom_group(self, name, *policies):
        """Create a group bundling the policies of these names; return its status and id."""
        p = self.parameters
        listed = self.call(p.GET, p.POLICIES_PATH).json()
        ids = [
            next(policy["id"] for policy in listed if policy["name"] == wanted)
            for wanted in policies
        ]
        created = self.call(p.POST, p.GROUPS_PATH, json={"name": name, "policy_ids": ids})
        return created.status_code, created.json().get("id")

    def access_row(self, user):
        """The access listing row of the user."""
        return next(
            row
            for row in self.call(self.parameters.GET, self.parameters.ACCESS_USERS_PATH).json()
            if row["id"] == user.id
        )

    def me(self, user):
        """The permissions the user sees for themselves."""
        self.bud.bud_sign_in_as(user)
        return set(
            self.call(self.parameters.GET, self.parameters.ME_PATH).json().get("permissions", [])
        )

    def rows(self, user):
        """How many memberships the user has."""
        return len(self.bud.bud_find_in_app(AccessGroupMember, user_id=user.id))

    def union(self):
        """A developer given two groups and a viewer given two others."""
        p = self.parameters
        boss, developer, viewer = self.people()
        self.bud.bud_sign_in_as(boss)
        checks = {}
        for name in (p.GROUP_STATIONS, p.GROUP_ACCESS):
            given = self.give(name, developer)
            checks[f"{name} given"] = (given.status_code, p.STATUS_CREATED)
            checks[f"{name} lists the developer once"] = (
                [m["user_id"] for m in given.json().get("members", [])],
                [developer.id],
            )
        groups = {g["name"]: g for g in self.call(p.GET, p.GROUPS_PATH).json()}
        expected = (
            base_role_permissions(UserRole.developer)
            | set(groups[p.GROUP_STATIONS]["permissions"])
            | set(groups[p.GROUP_ACCESS]["permissions"])
        )
        row = self.access_row(developer)
        checks["developer's groups"] = (
            [g["name"] for g in row["groups"]],
            [p.GROUP_ACCESS, p.GROUP_STATIONS],
        )
        checks["developer holds the union"] = (set(row["permissions"]), expected)
        checks["developer manages stations and access"] = (
            p.GROUP_MANAGED <= set(row["permissions"]),
            True,
        )
        checks["developer keeps the base role"] = (row["role"], "developer")
        checks["developer sees the union"] = (self.me(developer), expected)
        self.bud.bud_sign_in_as(boss)
        checks["viewer given two groups"] = (
            [self.give(name, viewer).status_code for name in p.OVERLAP_VIEWER_GROUPS],
            [p.STATUS_CREATED] * 2,
        )
        checks["viewer holds both groups' access"] = (
            p.OVERLAP_VIEWER_HELD <= self.me(viewer),
            True,
        )
        return checks

    def removal(self):
        """Take a developer's two groups away one at a time."""
        p = self.parameters
        boss, developer, _ = self.people()
        self.bud.bud_sign_in_as(boss)
        self.give(p.GROUP_STATIONS, developer)
        self.give(p.GROUP_ACCESS, developer)
        checks = {"first taken": (self.take(p.GROUP_STATIONS, developer).status_code, p.STATUS_OK)}
        row = self.access_row(developer)
        checks["shared permission kept"] = (p.GROUP_MANAGED <= set(row["permissions"]), True)
        checks["one group left"] = ([g["name"] for g in row["groups"]], [p.GROUP_ACCESS])
        checks["second taken"] = (self.take(p.GROUP_ACCESS, developer).status_code, p.STATUS_OK)
        row = self.access_row(developer)
        checks["management gone"] = (p.GROUP_MANAGED & set(row["permissions"]), set())
        checks["base allowance left"] = (
            set(row["permissions"]),
            base_role_permissions(UserRole.developer),
        )
        checks["base role and no group"] = ((row["role"], row["groups"]), ("developer", []))
        checks["taking it again"] = (
            self.take(p.GROUP_ACCESS, developer).status_code,
            p.STATUS_NOT_FOUND,
        )
        return checks

    def duplicate(self):
        """Give a viewer the same group twice."""
        p = self.parameters
        boss, _, viewer = self.people()
        self.bud.bud_sign_in_as(boss)
        first = self.give(p.GROUP_OPERATORS, viewer).status_code
        events = len(self.bud.bud_find_in_app(AuditEvent, action=p.OVERLAP_MEMBER_ADDED))
        again = self.give(p.GROUP_OPERATORS, viewer)
        return {
            "first given": (first, p.STATUS_CREATED),
            "again refused": (
                (again.status_code, again.json()),
                (p.STATUS_CONFLICT, {"detail": p.OVERLAP_DUPLICATE}),
            ),
            "one membership": (self.rows(viewer), 1),
            "one audit event": (
                (events, len(self.bud.bud_find_in_app(AuditEvent, action=p.OVERLAP_MEMBER_ADDED))),
                (1, 1),
            ),
        }

    def routes(self):
        """Two custom groups open two routes to a viewer; each closes with its group."""
        p = self.parameters
        boss, _, viewer = self.people()
        self.bud.bud_sign_in_as(boss)
        catalogue_status, catalogue = self.custom_group("Catalogue", "Products")
        configuration_status, configuration = self.custom_group(
            "Configuration", "Settings and integrations"
        )
        checks = {
            "groups created": (
                (catalogue_status, configuration_status),
                (p.STATUS_CREATED, p.STATUS_CREATED),
            ),
            "both given": (
                (
                    self.give(catalogue, viewer).status_code,
                    self.give(configuration, viewer).status_code,
                ),
                (p.STATUS_CREATED, p.STATUS_CREATED),
            ),
        }
        product = lambda name: self.call(p.POST, p.PRODUCTS_PATH, json={"name": name}).status_code
        setting = lambda: self.call(p.PUT, p.SETTING_X_PATH, json={"value": "y"}).status_code
        self.bud.bud_sign_in_as(viewer)
        checks["products open"] = (product("Probe") != p.STATUS_FORBIDDEN, True)
        checks["settings open"] = (setting() != p.STATUS_FORBIDDEN, True)
        self.bud.bud_sign_in_as(boss)
        checks["catalogue taken"] = (self.take(catalogue, viewer).status_code, p.STATUS_OK)
        self.bud.bud_sign_in_as(viewer)
        checks["products closed"] = (product("Probe two"), p.STATUS_FORBIDDEN)
        checks["settings still open"] = (setting() != p.STATUS_FORBIDDEN, True)
        self.bud.bud_sign_in_as(boss)
        checks["configuration taken"] = (self.take(configuration, viewer).status_code, p.STATUS_OK)
        self.bud.bud_sign_in_as(viewer)
        checks["settings closed"] = (setting(), p.STATUS_FORBIDDEN)
        return checks

    def deletion(self):
        """Delete one of a developer's three groups."""
        p = self.parameters
        boss, developer, _ = self.people()
        self.bud.bud_sign_in_as(boss)
        _, doomed = self.custom_group("Short lived", "Products")
        self.custom_group("Long lived", "Audit log")
        given = [
            self.give(doomed, developer).status_code,
            self.give("Long lived", developer).status_code,
            self.give(p.GROUP_OPERATORS, developer).status_code,
        ]
        deleted = self.call(p.DELETE, p.GROUP_PATH.format(doomed)).status_code
        row = self.access_row(developer)
        return {
            "three given": (given, [p.STATUS_CREATED] * 3),
            "group deleted": (deleted, p.STATUS_NO_CONTENT),
            "other groups kept": (
                [g["name"] for g in row["groups"]],
                ["Long lived", p.GROUP_OPERATORS],
            ),
            "base role kept": (row["role"], "developer"),
            "kept group's access": ("audit.view" in row["permissions"], True),
            "deleted group's access gone": ("products.manage" in row["permissions"], False),
            "two memberships": (self.rows(developer), 2),
        }

    def request(self):
        """Grant two access requests of a viewer with the same group."""
        p = self.parameters
        boss, _, viewer = self.people()
        runs = [
            self.bud.bud_add_to_app(TestRun(name=name, test_case_list="a", status="Completed"))
            for name in ("suite", "other suite")
        ]
        self.bud.bud_sign_in_as(boss)
        checks = {
            "readers given": (self.give(p.GROUP_READERS, viewer).status_code, p.STATUS_CREATED)
        }
        operators = self.group_id(p.GROUP_OPERATORS)
        decisions = []
        with mock.patch.object(access_requests, "send_access_request_email", return_value=None):
            for run in runs:
                self.bud.bud_sign_in_as(viewer)
                created = self.call(
                    p.POST,
                    p.ACCESS_REQUESTS_PATH,
                    json={"resource_type": "publish-to-bloom", "resource_ref": str(run.id)},
                )
                checks[f"request for {run.name}"] = (created.status_code, p.STATUS_CREATED)
                decisions.append(p.ACCESS_DECISION_PATH.format(created.json().get("id")))
        self.bud.bud_sign_in_as(boss)
        granted = self.call(
            p.POST, decisions[0], json={"decision": "granted", "group_id": operators}
        )
        checks["first granted"] = (
            (granted.status_code, granted.json().get("status")),
            (p.STATUS_OK, "granted"),
        )
        checks["group added beside the other"] = (
            [g["name"] for g in self.access_row(viewer)["groups"]],
            [p.GROUP_READERS, p.GROUP_OPERATORS],
        )
        again = self.call(p.POST, decisions[1], json={"decision": "granted", "group_id": operators})
        checks["second granted"] = (
            (again.status_code, again.json().get("status")),
            (p.STATUS_OK, "granted"),
        )
        checks["two memberships"] = (self.rows(viewer), 2)
        checks["operators held"] = (
            len(self.bud.bud_find_in_app(AccessGroupMember, group_id=operators, user_id=viewer.id)),
            1,
        )
        return checks

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    GroupOverlapApiTest().run()
