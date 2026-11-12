"""
* @file     ${tests/api/BUD_groups_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Access is a base role plus the policies of every group; defaults are read-only; givers hold what they give.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests each scenario on a fresh app database, signing in as the administrator or a seeded person.
"""

from datetime import datetime
from unittest import mock

from sqlalchemy import func, select

from app.api import access_requests
from app.core import access
from app.models import Artifact, Product, Runner, TestRun
from app.models.access import AccessGroup, AccessGroupMember, Policy
from app.models.user import User, UserRole
from tests.api.groups_api import GroupsApiBase


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


def person(email, name, role):
    """A person who is not stored yet."""
    return User(
        email=email,
        full_name=name,
        hashed_password="x",
        role=UserRole(role),
        is_active=True,
        session_version=1,
    )


class GroupsApiTest(GroupsApiBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.tc_checks = {}
        self.sent = []
        patch = mock.patch.object(
            access_requests, "send_access_request_email", lambda **mail: self.sent.append(mail)
        )
        patch.start()
        for scenario in (
            self.defaults,
            self.custom_groups,
            self.contract,
            self.policies,
            self.base_role,
            self.recipients,
            self.managers,
            self.hide_nothing,
            self.route_map,
            self.grant,
            self.admins_told,
            self.custom_policy,
            self.pictures,
        ):
            self.fresh()
            scenario()
        for scenario in (self.seed_rows, self.seed_administration, self.seed_publishing):
            self.fresh()
            self.bud.bud_await(scenario(self.bud.bud_open_session(on_app=True)))
        patch.stop()

    def fresh(self):
        """A fresh app signed in as the administrator, with no captured mail."""
        self.bud.bud_start_app()
        self.sent.clear()
        self.admin = User(
            id=self.parameters.TEST_ADMIN_ID,
            email=self.parameters.TEST_ADMIN_EMAIL,
            full_name=self.parameters.TEST_ADMIN_NAME,
            hashed_password="x",
            role=UserRole.admin,
            is_active=True,
            session_version=1,
        )

    def seed(self):
        """Two products, a viewer, a developer, a station, three runs and an artifact."""
        add = self.bud.bud_add_to_app
        first, second = add(Product(name="Gateway")), add(Product(name="Sensor"))
        viewer = add(person("viewer@example.com", "Val Viewer", "viewer"))
        developer = add(person("dev@example.com", "Dee Developer", "developer"))
        station = add(Runner(account="station-1", password_hash="x", token="t", socket_port=53100))
        runs = [
            add(
                TestRun(
                    name="gateway-suite",
                    test_case_list="a",
                    status="Running",
                    product_id=first.id,
                    runner_id=station.id,
                    started_at=datetime.utcnow(),
                )
            ),
            add(
                TestRun(
                    name="sensor-suite",
                    test_case_list="b",
                    status="Completed",
                    product_id=second.id,
                )
            ),
            add(TestRun(name="loose-suite", test_case_list="c", status="Completed")),
        ]
        artifact = add(
            Artifact(
                filename="log.txt",
                original_filename="log.txt",
                content_type="text/plain",
                size_bytes=3,
                storage_path="log.txt",
                test_run_id=runs[1].id,
            )
        )
        return first, second, viewer, developer, runs, artifact

    def call(self, method, path, body=None):
        """One request to the started app."""
        return self.bud.bud_request(method, path, json=body)

    def get(self, path):
        """Read one answer from the started app."""
        return body_of(self.call(self.parameters.GET, path))

    def group_id(self, name):
        """The id of a group by name."""
        groups = self.get(self.parameters.GROUPS_PATH)
        return next(
            (
                g.get("id")
                for g in (groups if isinstance(groups, list) else [])
                if g.get("name") == name
            ),
            0,
        )

    def policy_id(self, name):
        """The id of a policy by name."""
        policies = self.get(self.parameters.POLICIES_PATH_ALL)
        return next(
            (
                x.get("id")
                for x in (policies if isinstance(policies, list) else [])
                if x.get("name") == name
            ),
            0,
        )

    def give(self, group, user):
        """Give a group to a person."""
        return self.call(
            self.parameters.POST,
            f"{self.parameters.GROUPS_PATH}/{self.group_id(group)}/members",
            {"user_id": user.id},
        )

    def status(self, method, path, body=None):
        """The status code of one request."""
        return self.call(method, path, body).status_code

    def permissions(self):
        """The permissions of the signed-in person."""
        return body_of(self.call(self.parameters.GET, "/api/auth/me")).get("permissions") or []

    def defaults(self):
        p = self.parameters
        groups = self.get(p.GROUPS_PATH)
        groups = groups if isinstance(groups, list) else []
        bundles = {
            g.get("name"): sorted(x.get("name") for x in g.get("policies", [])) for g in groups
        }
        policies = self.get(p.POLICIES_PATH_ALL)
        policies = policies if isinstance(policies, list) else []
        operators, results = self.group_id("Test Operators"), self.policy_id("Results")
        checks = {
            "the default groups ship": (
                sorted(g.get("name") for g in groups),
                sorted(p.GROUPS_DEFAULT),
            ),
            "every shipped group is a default": (all(g.get("is_default") for g in groups), True),
            "the administrators group holds eight policies": (
                len(bundles.get("Application Administrators", [])),
                8,
            ),
            "the default policies ship in order": (
                [x.get("name") for x in policies],
                p.GROUPS_DEFAULT_POLICIES,
            ),
            "every shipped policy is a default": (all(x.get("is_default") for x in policies), True),
            "a default group cannot be renamed": (
                self.status(p.PATCH, f"{p.GROUPS_PATH}/{operators}", {"name": "X"}),
                p.STATUS_CONFLICT,
            ),
            "a default group cannot be deleted": (
                self.status(p.DELETE, f"{p.GROUPS_PATH}/{operators}"),
                p.STATUS_CONFLICT,
            ),
            "a default policy cannot be renamed": (
                self.status(p.PATCH, f"{p.POLICIES_PATH_ALL}/{results}", {"name": "X"}),
                p.STATUS_CONFLICT,
            ),
            "a default policy cannot be deleted": (
                self.status(p.DELETE, f"{p.POLICIES_PATH_ALL}/{results}"),
                p.STATUS_CONFLICT,
            ),
        }
        for name, bundle in p.GROUPS_BUNDLES.items():
            checks[f"{name} bundles its policies"] = (bundles.get(name), bundle)
        copy = self.call(p.POST, f"{p.GROUPS_PATH}/{operators}/duplicate")
        copied = body_of(copy)
        renamed = body_of(
            self.call(p.PATCH, f"{p.GROUPS_PATH}/{copied.get('id')}", {"name": "Night shift"})
        )
        policy_copy = body_of(self.call(p.POST, f"{p.POLICIES_PATH_ALL}/{results}/duplicate"))
        checks.update(
            {
                "a default group is duplicated": (copy.status_code, p.STATUS_CREATED),
                "the copy is a custom group without members": (
                    (copied.get("name"), copied.get("is_default"), copied.get("members")),
                    ("Test Operators (copy)", False, []),
                ),
                "the copy is renamed": (renamed.get("name"), "Night shift"),
                "a default policy is duplicated as a custom one": (
                    (policy_copy.get("name"), policy_copy.get("is_default")),
                    ("Results (copy)", False),
                ),
            }
        )
        self.tc_checks["defaults"] = checks

    def custom_groups(self):
        p = self.parameters
        _, _, viewer, _, _, _ = self.seed()
        ids = [self.policy_id("Results"), self.policy_id("Custom runs")]
        created = self.call(p.POST, p.GROUPS_PATH, {"name": "Lab", "policy_ids": ids})
        group_id = body_of(created).get("id")
        members = f"{p.GROUPS_PATH}/{group_id}/members"
        taken = self.status(p.POST, p.GROUPS_PATH, {"name": "Lab"})
        unknown_policy = self.status(p.POST, p.GROUPS_PATH, {"name": "Bad", "policy_ids": [999]})
        member = self.call(p.POST, members, {"user_id": viewer.id})
        twice = self.status(p.POST, members, {"user_id": viewer.id})
        unknown_person = self.status(p.POST, members, {"user_id": 999})
        changed = body_of(
            self.call(
                p.PATCH,
                f"{p.GROUPS_PATH}/{group_id}",
                {"name": "Lab A", "description": "Bench", "policy_ids": [ids[0]]},
            )
        )
        self.call(p.POST, p.GROUPS_PATH, {"name": "Other"})
        self.tc_checks["custom groups"] = {
            "a group is created": (created.status_code, p.STATUS_CREATED),
            "the group holds its policies' permissions": (
                body_of(created).get("permissions"),
                p.GROUPS_LAB_PERMISSIONS,
            ),
            "a taken name is refused": (taken, p.STATUS_CONFLICT),
            "an unknown policy is refused": (unknown_policy, p.STATUS_UNPROCESSABLE),
            "a member is added": (member.status_code, p.STATUS_CREATED),
            "the member is listed": (
                body_of(member).get("members"),
                [
                    {
                        "user_id": viewer.id,
                        "email": "viewer@example.com",
                        "full_name": "Val Viewer",
                        "role": "viewer",
                        "profile_picture_url": None,
                    }
                ],
            ),
            "a member is not added twice": (twice, p.STATUS_CONFLICT),
            "an unknown person is not found": (unknown_person, p.STATUS_NOT_FOUND),
            "the group is renamed and described": (
                (changed.get("name"), changed.get("description")),
                ("Lab A", "Bench"),
            ),
            "the group keeps the chosen policy": (
                [x.get("name") for x in changed.get("policies", [])],
                ["Results"],
            ),
            "renaming onto a taken name is refused": (
                self.status(p.PATCH, f"{p.GROUPS_PATH}/{group_id}", {"name": "Other"}),
                p.STATUS_CONFLICT,
            ),
            "a member is removed": (
                body_of(self.call(p.DELETE, f"{members}/{viewer.id}")).get("members"),
                [],
            ),
            "a removed member is not found": (
                self.status(p.DELETE, f"{members}/{viewer.id}"),
                p.STATUS_NOT_FOUND,
            ),
            "the group is deleted": (
                self.status(p.DELETE, f"{p.GROUPS_PATH}/{group_id}"),
                p.STATUS_NO_CONTENT,
            ),
            "a deleted group is not found": (
                self.status(p.DELETE, f"{p.GROUPS_PATH}/{group_id}"),
                p.STATUS_NOT_FOUND,
            ),
        }

    def contract(self):
        p = self.parameters
        self.tc_checks["contract"] = {
            f"{payload} is refused": (
                self.status(p.POST, p.GROUPS_PATH, {"name": "Invalid", **payload}),
                p.STATUS_UNPROCESSABLE,
            )
            for payload in p.GROUPS_BAD_PAYLOADS
        }

    def policies(self):
        p = self.parameters
        rows = self.get(f"{p.POLICIES_PATH_ALL}/catalogue")
        catalogue = {
            row.get("resource"): row.get("actions")
            for row in (rows if isinstance(rows, list) else [])
        }
        created = self.call(
            p.POST,
            p.POLICIES_PATH_ALL,
            {"name": "Station keys", "permissions": {"stations": ["manage", "view"]}},
        )
        policy_id = body_of(created).get("id")
        group = body_of(
            self.call(p.POST, p.GROUPS_PATH, {"name": "Keys", "policy_ids": [policy_id]})
        )
        in_use = self.status(p.DELETE, f"{p.POLICIES_PATH_ALL}/{policy_id}")
        self.call(p.DELETE, f"{p.GROUPS_PATH}/{group.get('id')}")
        self.tc_checks["policies"] = {
            "the catalogue lists the station actions": (
                catalogue.get("stations"),
                ["view", "manage"],
            ),
            "the catalogue lists the access action": (catalogue.get("access"), ["manage"]),
            "a policy is created": (created.status_code, p.STATUS_CREATED),
            "the policy keeps the catalogue order": (
                body_of(created).get("permissions"),
                {"stations": ["view", "manage"]},
            ),
            "a taken name is refused": (
                self.status(p.POST, p.POLICIES_PATH_ALL, {"name": "Station keys"}),
                p.STATUS_CONFLICT,
            ),
            "an unknown resource is refused": (
                self.status(
                    p.POST, p.POLICIES_PATH_ALL, {"name": "Bad", "permissions": {"users": ["edit"]}}
                ),
                p.STATUS_UNPROCESSABLE,
            ),
            "an unknown action is refused": (
                self.status(
                    p.POST,
                    p.POLICIES_PATH_ALL,
                    {"name": "Bad", "permissions": {"stations": ["delete"]}},
                ),
                p.STATUS_UNPROCESSABLE,
            ),
            "a policy in use is kept": (in_use, p.STATUS_CONFLICT),
            "an unused policy is deleted": (
                self.status(p.DELETE, f"{p.POLICIES_PATH_ALL}/{policy_id}"),
                p.STATUS_NO_CONTENT,
            ),
        }

    def base_role(self):
        p = self.parameters
        _, _, viewer, _, runs, _ = self.seed()
        custom = "/api/test-runs/custom"
        self.give("Results Viewers", viewer)
        self.bud.bud_sign_in_as(viewer)
        me = body_of(self.call(p.GET, "/api/auth/me"))
        before = self.status(p.POST, custom, {"test_paths": ["a.B"]})
        self.bud.bud_sign_in_as(self.admin)
        self.give("Test Operators", viewer)
        operators = self.group_id("Test Operators")
        self.bud.bud_sign_in_as(viewer)
        held = self.permissions()
        role = body_of(self.call(p.GET, "/api/auth/me")).get("role")
        queued = self.call(p.POST, custom, {"test_paths": ["a.B"]})
        deleted = self.status(p.DELETE, f"{p.TEST_RUNS_PATH}/{runs[1].id}")
        groups = self.status(p.GET, p.GROUPS_PATH)
        self.bud.bud_sign_in_as(self.admin)
        self.call(p.DELETE, f"{p.GROUPS_PATH}/{operators}/members/{viewer.id}")
        self.bud.bud_sign_in_as(viewer)
        self.tc_checks["base role"] = {
            "the viewer stays a viewer": (me.get("role"), "viewer"),
            "results viewers cannot queue runs": (
                "custom_runs.create" in (me.get("permissions") or []),
                False,
            ),
            "a queued run is refused": (before, p.STATUS_FORBIDDEN),
            "the role stays with the second group": (role, "viewer"),
            "test operators queue and publish": (
                {"custom_runs.create", "bloom_publish.execute"} <= set(held),
                True,
            ),
            "a queued run reaches validation": (queued.status_code, p.STATUS_UNPROCESSABLE),
            "the validation names the test cases": (
                str(body_of(queued).get("detail")).startswith(
                    "None of the selected test cases can be run"
                ),
                True,
            ),
            "deleting a run stays refused": (deleted, p.STATUS_FORBIDDEN),
            "the groups stay hidden": (groups, p.STATUS_FORBIDDEN),
            "removing the group takes its permission": (
                "custom_runs.create" in self.permissions(),
                False,
            ),
            "a queued run is refused again": (
                self.status(p.POST, custom, {"test_paths": ["a.B"]}),
                p.STATUS_FORBIDDEN,
            ),
        }

    def recipients(self):
        p = self.parameters
        checks = {}
        for group in p.GROUPS_STATION_GROUPS:
            for role in p.GROUPS_RECIPIENT_ROLES:
                self.fresh()
                recipient = self.bud.bud_add_to_app(
                    person("recipient@example.com", "Recipient", role)
                )
                account = (
                    recipient.id,
                    recipient.email,
                    recipient.full_name,
                    recipient.role,
                    recipient.is_active,
                )
                group_id = self.group_id(group)
                response = self.call(
                    p.POST, f"{p.GROUPS_PATH}/{group_id}/members", {"user_id": recipient.id}
                )
                key = f"{group} for a {role}"
                held = lambda: len(
                    self.bud.bud_find_in_app(
                        AccessGroupMember, group_id=group_id, user_id=recipient.id
                    )
                )
                if role == "viewer":
                    checks[f"{key}: the viewer is refused"] = (
                        response.status_code,
                        p.STATUS_UNPROCESSABLE,
                    )
                    checks[f"{key}: no membership is stored"] = (held(), 0)
                else:
                    checks[f"{key}: the member is added"] = (response.status_code, p.STATUS_CREATED)
                    checks[f"{key}: the member is listed"] = (
                        body_of(response).get("members"),
                        [
                            {
                                "user_id": recipient.id,
                                "email": recipient.email,
                                "full_name": recipient.full_name,
                                "role": role,
                                "profile_picture_url": None,
                            }
                        ],
                    )
                    checks[f"{key}: the membership is stored"] = (held(), 1)
                    removed = self.call(
                        p.DELETE, f"{p.GROUPS_PATH}/{group_id}/members/{recipient.id}"
                    )
                    checks[f"{key}: the member is removed"] = (removed.status_code, p.STATUS_OK)
                    checks[f"{key}: no member is left"] = (body_of(removed).get("members"), [])
                    checks[f"{key}: the membership is gone"] = (held(), 0)
                stored = (self.bud.bud_find_in_app(User, id=recipient.id) or [User()])[0]
                checks[f"{key}: the account is unchanged"] = (
                    (stored.id, stored.email, stored.full_name, stored.role, stored.is_active),
                    account,
                )
        self.tc_checks["recipients"] = checks

    def managers(self):
        p = self.parameters
        _, _, viewer, developer, _, _ = self.seed()
        checks = {
            "a viewer is not an access manager": (
                self.give("Access Managers", viewer).status_code,
                p.STATUS_UNPROCESSABLE,
            ),
            "a viewer is not a station manager": (
                self.give("Station Managers", viewer).status_code,
                p.STATUS_UNPROCESSABLE,
            ),
            "a developer becomes an access manager": (
                self.give("Access Managers", developer).status_code,
                p.STATUS_CREATED,
            ),
        }
        managers_id = self.group_id("Access Managers")
        self.bud.bud_sign_in_as(developer)
        rows = self.get("/api/access/users")
        users = {u.get("email"): u for u in (rows if isinstance(rows, list) else [])}
        stations, products, settings_id = (
            self.policy_id("Stations"),
            self.policy_id("Products"),
            self.policy_id("Settings and integrations"),
        )
        own = self.call(p.POST, p.GROUPS_PATH, {"name": "Bench crew", "policy_ids": [stations]})
        checks.update(
            {
                "the manager lists groups": (self.status(p.GET, p.GROUPS_PATH), p.STATUS_OK),
                "the manager lists policies": (
                    self.status(p.GET, p.POLICIES_PATH_ALL),
                    p.STATUS_OK,
                ),
                "the roster names the manager's group": (
                    users.get("dev@example.com", {}).get("groups"),
                    [{"id": managers_id, "name": "Access Managers"}],
                ),
                "the roster names the manager's permission": (
                    "access.manage" in users.get("dev@example.com", {}).get("permissions", []),
                    True,
                ),
                "the roster names the viewer's permissions": (
                    users.get("viewer@example.com", {}).get("permissions"),
                    p.GROUPS_VIEWER_PERMISSIONS,
                ),
                "the manager gives what they hold": (
                    self.give("Test Operators", viewer).status_code,
                    p.STATUS_CREATED,
                ),
                "the manager cannot give administration to a viewer": (
                    self.give("Application Administrators", viewer).status_code,
                    p.STATUS_FORBIDDEN,
                ),
                "the manager cannot give administration to themself": (
                    self.give("Application Administrators", developer).status_code,
                    p.STATUS_FORBIDDEN,
                ),
                "the manager cannot bundle products": (
                    self.status(p.POST, p.GROUPS_PATH, {"name": "P", "policy_ids": [products]}),
                    p.STATUS_FORBIDDEN,
                ),
                "the manager bundles stations": (own.status_code, p.STATUS_CREATED),
                "the manager cannot add settings": (
                    self.status(
                        p.PATCH,
                        f"{p.GROUPS_PATH}/{body_of(own).get('id')}",
                        {"policy_ids": [settings_id]},
                    ),
                    p.STATUS_FORBIDDEN,
                ),
                "the manager cannot create policies": (
                    self.status(p.POST, p.POLICIES_PATH_ALL, {"name": "Mine"}),
                    p.STATUS_FORBIDDEN,
                ),
                "the manager cannot list users": (
                    self.status(p.GET, "/api/users"),
                    p.STATUS_FORBIDDEN,
                ),
                "the manager cannot invite": (
                    self.status(
                        p.POST, "/api/users/invite", {"email": "x@example.com", "full_name": "X"}
                    ),
                    p.STATUS_FORBIDDEN,
                ),
            }
        )
        self.bud.bud_sign_in_as(self.admin)
        checks["the administrator gives administration"] = (
            self.give("Application Administrators", developer).status_code,
            p.STATUS_CREATED,
        )
        self.bud.bud_sign_in_as(developer)
        administrators = self.group_id("Application Administrators")
        checks["administration cannot be given again by its holder"] = (
            self.give("Application Administrators", developer).status_code,
            p.STATUS_FORBIDDEN,
        )
        checks["administration cannot be removed by its holder"] = (
            self.status(p.DELETE, f"{p.GROUPS_PATH}/{administrators}/members/{developer.id}"),
            p.STATUS_FORBIDDEN,
        )
        self.tc_checks["managers"] = checks

    def hide_nothing(self):
        p = self.parameters
        _, second, viewer, _, runs, artifact = self.seed()
        self.give("Results Viewers", viewer)
        self.bud.bud_sign_in_as(viewer)
        listed = self.get(p.TEST_RUNS_PATH).get("runs", [])
        products = self.get("/api/products")
        stations = self.get("/api/runners/status").get("runners") or [{}]
        checks = {
            "every run is listed": (
                sorted(r.get("name") for r in listed),
                ["gateway-suite", "loose-suite", "sensor-suite"],
            ),
            "every product is listed": (
                [x.get("name") for x in (products if isinstance(products, list) else [])],
                ["Gateway", "Sensor"],
            ),
            "a product is read": (self.status(p.GET, f"/api/products/{second.id}"), p.STATUS_OK),
            "the statistics count every run": (self.get(p.RUN_STATS_PATH).get("total_runs"), 3),
            "an artifact is read": (
                self.status(p.GET, f"/api/uploads/info/{artifact.id}"),
                p.STATUS_OK,
            ),
            "the station shows its current run": (
                ((stations[0] or {}).get("current_run") or {}).get("name"),
                "gateway-suite",
            ),
            "the groups stay hidden": (self.status(p.GET, p.GROUPS_PATH), p.STATUS_FORBIDDEN),
        }
        for run in runs:
            checks[f"the run {run.name} is read"] = (
                self.status(p.GET, f"{p.TEST_RUNS_PATH}/{run.id}"),
                p.STATUS_OK,
            )
        self.tc_checks["hide nothing"] = checks

    def route_map(self):
        p = self.parameters
        checks = {}
        for who, allowed in p.GROUPS_ALLOWED.items():
            self.fresh()
            first, _, viewer, developer, runs, artifact = self.seed()
            if who == "station_manager":
                self.give("Station Managers", developer)
            actor = {
                "viewer": viewer,
                "developer": developer,
                "station_manager": developer,
                "admin": self.admin,
            }[who]
            self.bud.bud_sign_in_as(actor)
            for permission, method, path, body in p.GROUPS_WRITES:
                url = path.format(
                    run=runs[1].id, artifact=artifact.id, product=first.id, viewer=viewer.id
                )
                refused = self.status(method, url, body) == p.STATUS_FORBIDDEN
                checks[
                    f"{who}: {method} {path} is {'refused' if permission not in allowed else 'allowed'}"
                ] = (refused, permission not in allowed)
        self.tc_checks["route map"] = checks

    def grant(self):
        p = self.parameters
        _, _, viewer, developer, runs, _ = self.seed()
        self.give("Access Managers", developer)
        self.bud.bud_sign_in_as(viewer)
        request = self.call(
            p.POST,
            p.ACCESS_REQUESTS_PATH,
            {"resource_type": "publish-to-bloom", "resource_ref": str(runs[1].id)},
        )
        mailed = sorted(mail.get("to_email") for mail in self.sent)
        viewer_list = self.status(p.GET, p.ACCESS_REQUESTS_PATH)
        self.bud.bud_sign_in_as(developer)
        pending = self.get(p.ACCESS_REQUESTS_PATH)
        pending = pending if isinstance(pending, list) else [{}]
        decision = p.ACCESS_DECISION_PATH.format((pending or [{}])[0].get("id"))
        without_group = self.status(p.POST, decision, {"decision": "granted"})
        readers = self.status(
            p.POST, decision, {"decision": "granted", "group_id": self.group_id("Results Viewers")}
        )
        granted = self.call(
            p.POST, decision, {"decision": "granted", "group_id": self.group_id("Test Operators")}
        )
        again = self.status(p.POST, decision, {"decision": "refused"})
        self.bud.bud_sign_in_as(viewer)
        self.tc_checks["grant"] = {
            "the request is created": (request.status_code, p.STATUS_CREATED),
            "the administrators and managers are mailed": (
                mailed,
                ["admin@example.com", "dev@example.com"],
            ),
            "the viewer cannot list requests": (viewer_list, p.STATUS_FORBIDDEN),
            "the manager lists the request": (
                [row.get("requester_email") for row in pending],
                ["viewer@example.com"],
            ),
            "a grant without a group is refused": (without_group, p.STATUS_UNPROCESSABLE),
            "a grant with a group lacking the permission is refused": (
                readers,
                p.STATUS_UNPROCESSABLE,
            ),
            "a grant with test operators succeeds": (granted.status_code, p.STATUS_OK),
            "the request is granted": (body_of(granted).get("status"), "granted"),
            "a second decision is a conflict": (again, p.STATUS_CONFLICT),
            "the viewer now publishes": ("bloom_publish.execute" in self.permissions(), True),
        }

    def admins_told(self):
        p = self.parameters
        _, _, viewer, _, runs, _ = self.seed()
        self.bud.bud_add_to_app(person("boss@example.com", "Bo Boss", "admin"))
        self.bud.bud_sign_in_as(viewer)
        self.call(
            p.POST,
            p.ACCESS_REQUESTS_PATH,
            {"resource_type": "publish-to-bloom", "resource_ref": str(runs[0].id)},
        )
        self.tc_checks["admins told"] = {
            "every administrator is mailed": (
                sorted(mail.get("to_email") for mail in self.sent),
                ["admin@example.com", "boss@example.com"],
            ),
        }

    def custom_policy(self):
        p = self.parameters
        _, _, _, developer, _, _ = self.seed()
        policy = body_of(
            self.call(
                p.POST,
                p.POLICIES_PATH_ALL,
                {
                    "name": "Back office",
                    "permissions": {
                        "products": ["manage"],
                        "settings": ["view", "edit"],
                        "audit": ["view"],
                    },
                },
            )
        )
        group = body_of(
            self.call(
                p.POST, p.GROUPS_PATH, {"name": "Back office", "policy_ids": [policy.get("id")]}
            )
        )
        self.bud.bud_sign_in_as(developer)
        before = (
            self.status(p.POST, "/api/products", {"name": "Probe"}),
            self.status(p.GET, "/api/audit"),
        )
        self.bud.bud_sign_in_as(self.admin)
        given = self.status(
            p.POST, f"{p.GROUPS_PATH}/{group.get('id')}/members", {"user_id": developer.id}
        )
        self.bud.bud_sign_in_as(developer)
        self.tc_checks["custom policy"] = {
            "products stay closed before the group": (before[0], p.STATUS_FORBIDDEN),
            "the audit stays closed before the group": (before[1], p.STATUS_FORBIDDEN),
            "the group is given": (given, p.STATUS_CREATED),
            "products open with the group": (
                self.status(p.POST, "/api/products", {"name": "Probe"}),
                p.STATUS_CREATED,
            ),
            "settings open with the group": (self.status(p.GET, "/api/settings"), p.STATUS_OK),
            "settings writes open with the group": (
                self.status(p.PUT, "/api/settings/x", {"value": "y"}) != p.STATUS_FORBIDDEN,
                True,
            ),
            "the audit opens with the group": (self.status(p.GET, "/api/audit"), p.STATUS_OK),
            "users stay closed": (self.status(p.GET, "/api/users"), p.STATUS_FORBIDDEN),
            "groups stay closed": (self.status(p.GET, p.GROUPS_PATH), p.STATUS_FORBIDDEN),
        }

    def pictures(self):
        _, _, _, developer, _, _ = self.seed()
        developer.profile_picture = b"stored-profile-image"
        developer = self.bud.bud_add_to_app(developer)
        group = body_of(self.give("Test Operators", developer))
        member = next(
            (item for item in group.get("members", []) if item.get("user_id") == developer.id), {}
        )
        roster = self.get("/api/access/users")
        listed = next(
            (
                item
                for item in (roster if isinstance(roster, list) else [])
                if item.get("id") == developer.id
            ),
            {},
        )
        self.tc_checks["pictures"] = {
            "the group roster shows the picture": (
                member.get("profile_picture_url"),
                developer.profile_picture_url,
            ),
            "the access roster shows the picture": (
                listed.get("profile_picture_url"),
                developer.profile_picture_url,
            ),
        }

    async def seed_rows(self, db):
        await access.seed_default_access(db)
        await access.seed_default_access(db)
        self.tc_checks["seed rows"] = {
            "five groups are kept": (
                await db.scalar(select(func.count()).select_from(AccessGroup)),
                5,
            ),
            "eight policies are kept": (
                await db.scalar(select(func.count()).select_from(Policy)),
                8,
            ),
        }

    async def seed_administration(self, db):
        await access.seed_default_access(db)
        group = await db.scalar(
            select(AccessGroup).where(AccessGroup.system_key == "app_administration")
        )
        group.name = "App Administration"
        user = User(
            email="rename@example.com",
            full_name="Existing member",
            role=UserRole.developer,
            hashed_password="unused",
            is_active=True,
        )
        db.add(user)
        await db.flush()
        group_id, user_id = group.id, user.id
        db.add(AccessGroupMember(group_id=group_id, user_id=user_id))
        await db.flush()
        await access.seed_default_access(db)
        await access.seed_default_access(db)
        self.tc_checks["seed administration"] = {
            "the group keeps its id": (group.id, group_id),
            "the group gets its current name": (group.name, "Application Administrators"),
            "the group keeps its key": (group.system_key, "app_administration"),
            "the member is kept": (
                (await db.get(AccessGroupMember, {"group_id": group_id, "user_id": user_id}))
                is not None,
                True,
            ),
            "the member keeps their role": (user.role, UserRole.developer),
        }

    async def seed_publishing(self, db):
        await access.seed_default_access(db)
        policy = await db.scalar(select(Policy).where(Policy.system_key == "publish_to_bloom"))
        policy.name = "Publish to Bloom"
        policy_id, permissions = policy.id, dict(policy.permissions)
        group = await db.scalar(
            select(AccessGroup).where(AccessGroup.system_key == "test_operators")
        )
        group_id = group.id
        await db.flush()
        await access.seed_default_access(db)
        await access.seed_default_access(db)
        await db.refresh(group, attribute_names=["policies"])
        self.tc_checks["seed publishing"] = {
            "the policy keeps its id": (policy.id, policy_id),
            "the policy gets its current name": (policy.name, "Reports publishing"),
            "the policy keeps its permissions": (policy.permissions, permissions),
            "the group keeps its id": (group.id, group_id),
            "the group keeps the policy": (policy_id in [item.id for item in group.policies], True),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    GroupsApiTest().run()
