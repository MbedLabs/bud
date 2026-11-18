"""
* @file     ${tests/api/application_policies_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the application policies an administrator sets on a user, as Bloom does.
* @author   Amine El Omari
* @date     2026-11-18
* @version  1.0.0
* @note     Base class containing the bud methods of the application policies; each step starts its own app.
"""

from unittest import mock

from app.api import access_requests
from app.core.access import app_scoped, base_role_permissions, permission_set
from app.models import Product, ProductAccess, TestRun
from app.models.user import User, UserRole
from tests.bud_test_base import BudAppTestCase


class ApplicationPoliciesApiBase(BudAppTestCase):

    def people(self):
        """Start a fresh app signed in as an administrator, with a developer and a viewer."""
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
            for email, name, role in self.parameters.AP_PEOPLE
        ]

    def call(self, method, path, **kwargs):
        """Send one request as the signed-in person."""
        return self.bud.bud_request(method, path, **kwargs)

    def policy(self, name):
        """The policy of that name, as the policies listing answers it."""
        p = self.parameters
        return next(x for x in self.call(p.GET, p.POLICIES_PATH).json() if x["name"] == name)

    def set_policies(self, user, *names):
        """Set the user's application policies to the policies of these names."""
        p = self.parameters
        ids = [self.policy(name)["id"] for name in names]
        return self.call(p.PUT, p.AP_PATH.format(user.id), json={"policy_ids": ids})

    def held(self, user):
        """The permissions the access listing gives the user."""
        p = self.parameters
        row = next(r for r in self.call(p.GET, p.ACCESS_USERS_PATH).json() if r["id"] == user.id)
        return set(row["permissions"])

    def me(self, user):
        """The permissions the user sees for themselves."""
        self.bud.bud_sign_in_as(user)
        return set(self.call(self.parameters.GET, self.parameters.ME_PATH).json()["permissions"])

    def expected(self, role, *names):
        """The app-wide permissions of the base role and of the policies of these names."""
        names_held = set(base_role_permissions(role))
        for name in names:
            names_held |= permission_set(self.policy(name)["permissions"])
        return set(app_scoped(frozenset(names_held)))

    def bud_two_application_policies_give_their_union(self):
        p = self.parameters
        _, developer, viewer = self.people()
        given = self.set_policies(developer, p.AP_STATIONS, p.AP_ACCESS)
        expected = self.expected(UserRole.developer, p.AP_STATIONS, p.AP_ACCESS)
        listed = self.held(developer)
        self.set_policies(viewer, p.AP_PRODUCTS, p.AP_SETTINGS)
        viewer_held = self.held(viewer)
        self.print_variables({"given": given.json(), "listed": sorted(listed)})
        self.assertEqual(given.status_code, p.STATUS_OK, msg=p.MSG_AP_GIVEN, abort_on_fail=False)
        self.assertEqual(listed, expected, msg=p.MSG_AP_UNION, abort_on_fail=False)
        self.assertEqual(self.me(developer), expected, msg=p.MSG_AP_ME, abort_on_fail=False)
        self.assertEqual(
            p.AP_VIEWER_HELD <= viewer_held, True, msg=p.MSG_AP_VIEWER, abort_on_fail=False
        )

    def bud_removing_one_application_policy_keeps_the_other(self):
        p = self.parameters
        _, developer, _ = self.people()
        self.set_policies(developer, p.AP_STATIONS, p.AP_AUDIT)
        self.set_policies(developer, p.AP_AUDIT)
        one_left = self.held(developer)
        self.set_policies(developer)
        none_left = self.held(developer)
        self.print_variables({"one left": sorted(one_left), "none left": sorted(none_left)})
        self.assertEqual(
            ("stations.manage" in one_left, "audit.view" in one_left),
            (False, True),
            msg=p.MSG_AP_REMOVAL,
            abort_on_fail=False,
        )
        self.assertEqual(
            none_left,
            set(app_scoped(base_role_permissions(UserRole.developer))),
            msg=p.MSG_AP_BASE_LEFT,
            abort_on_fail=False,
        )

    def bud_an_application_policy_is_held_once(self):
        p = self.parameters
        _, developer, _ = self.people()
        audit = self.policy(p.AP_AUDIT)["id"]
        twice = self.call(
            p.PUT, p.AP_PATH.format(developer.id), json={"policy_ids": [audit, audit]}
        )
        self.set_policies(developer, p.AP_AUDIT)
        self.set_policies(developer, p.AP_AUDIT)
        stored = self.call(p.GET, p.AP_PATH.format(developer.id)).json()
        self.print_variables({"twice": twice.status_code, "stored": stored})
        self.assertEqual(
            twice.status_code, p.STATUS_UNPROCESSABLE, msg=p.MSG_AP_DUPLICATE, abort_on_fail=False
        )
        self.assertEqual(stored, {"policy_ids": [audit]}, msg=p.MSG_AP_ONCE, abort_on_fail=False)

    def bud_each_route_follows_the_application_policy_that_opens_it(self):
        p = self.parameters
        boss, _, viewer = self.people()
        product = lambda name: self.call(p.POST, p.PRODUCTS_PATH, json={"name": name}).status_code
        setting = lambda: self.call(p.PUT, p.SETTING_X_PATH, json={"value": "y"}).status_code
        self.set_policies(viewer, p.AP_PRODUCTS, p.AP_SETTINGS)
        self.bud.bud_sign_in_as(viewer)
        both_open = (product("Probe") != p.STATUS_FORBIDDEN, setting() != p.STATUS_FORBIDDEN)
        self.bud.bud_sign_in_as(boss)
        self.set_policies(viewer, p.AP_SETTINGS)
        self.bud.bud_sign_in_as(viewer)
        one_open = (product("Probe two"), setting() != p.STATUS_FORBIDDEN)
        self.bud.bud_sign_in_as(boss)
        self.set_policies(viewer)
        self.bud.bud_sign_in_as(viewer)
        none_open = setting()
        self.bud.bud_sign_in_as(boss)
        self.print_variables({"both": both_open, "one": one_open, "none": none_open})
        self.assertEqual(both_open, (True, True), msg=p.MSG_AP_ROUTES_OPEN, abort_on_fail=False)
        self.assertEqual(
            one_open, (p.STATUS_FORBIDDEN, True), msg=p.MSG_AP_ROUTE_CLOSED, abort_on_fail=False
        )
        self.assertEqual(
            none_open, p.STATUS_FORBIDDEN, msg=p.MSG_AP_ROUTES_CLOSED, abort_on_fail=False
        )

    def bud_a_held_application_policy_is_not_deleted(self):
        p = self.parameters
        _, developer, _ = self.people()
        created = self.call(p.POST, p.POLICIES_PATH, json=p.AP_CUSTOM_POLICY).json()
        self.call(p.PUT, p.AP_PATH.format(developer.id), json={"policy_ids": [created["id"]]})
        refused = self.call(p.DELETE, f"{p.POLICIES_PATH}/{created['id']}").status_code
        self.call(p.PUT, p.AP_PATH.format(developer.id), json={"policy_ids": []})
        deleted = self.call(p.DELETE, f"{p.POLICIES_PATH}/{created['id']}").status_code
        self.print_variables({"refused": refused, "deleted": deleted})
        self.assertEqual(
            (refused, deleted),
            (p.STATUS_CONFLICT, p.STATUS_NO_CONTENT),
            msg=p.MSG_AP_HELD_KEPT,
            abort_on_fail=False,
        )

    def bud_a_product_only_policy_is_not_an_application_policy(self):
        p = self.parameters
        _, developer, _ = self.people()
        answer = self.set_policies(developer, p.AP_CUSTOM_RUNS)
        self.print_variables({"answer": answer.json()})
        self.assertEqual(
            (answer.status_code, answer.json()),
            (p.STATUS_BAD_REQUEST, {"detail": p.AP_APP_ONLY}),
            msg=p.MSG_AP_APP_ONLY,
            abort_on_fail=False,
        )

    def bud_station_management_needs_an_administrator_or_developer(self):
        p = self.parameters
        _, developer, viewer = self.people()
        refused = self.set_policies(viewer, p.AP_STATIONS)
        given = self.set_policies(developer, p.AP_STATIONS)
        stored = self.call(p.GET, p.AP_PATH.format(viewer.id)).json()
        self.assertEqual(
            (refused.status_code, given.status_code, stored),
            (p.STATUS_UNPROCESSABLE, p.STATUS_OK, {"policy_ids": []}),
            msg=p.MSG_AP_STATIONS,
            abort_on_fail=False,
        )

    def bud_a_granted_request_leaves_the_application_policies(self):
        p = self.parameters
        boss, _, viewer = self.people()
        product = self.bud.bud_add_to_app(Product(name="Demo"))
        run = self.bud.bud_add_to_app(
            TestRun(name="suite", test_case_list="a", status="Completed", product_id=product.id)
        )
        operators = next(
            g["id"] for g in self.call(p.GET, p.GROUPS_PATH).json() if g["name"] == p.AP_OPERATORS
        )
        with mock.patch.object(access_requests, "send_access_request_email", return_value=None):
            self.bud.bud_sign_in_as(viewer)
            created = self.call(
                p.POST,
                p.ACCESS_REQUESTS_PATH,
                json={"resource_type": "publish-to-bloom", "resource_ref": str(run.id)},
            ).json()
        self.bud.bud_sign_in_as(boss)
        granted = self.call(
            p.POST,
            p.ACCESS_DECISION_PATH.format(created.get("id")),
            json={"decision": "granted", "group_id": operators},
        )
        policies = self.call(p.GET, p.AP_PATH.format(viewer.id)).json()
        on_product = self.bud.bud_find_in_app(
            ProductAccess, group_id=operators, user_id=viewer.id, product_id=product.id
        )
        self.assertEqual(
            (granted.status_code, policies, len(on_product)),
            (p.STATUS_OK, {"policy_ids": []}, 1),
            msg=p.MSG_AP_REQUEST,
            abort_on_fail=False,
        )

    def bud_only_an_administrator_reads_or_sets_application_policies(self):
        p = self.parameters
        _, developer, viewer = self.people()
        unknown = self.call(p.GET, p.AP_PATH.format(p.AP_UNKNOWN_ID)).status_code
        self.bud.bud_sign_in_as(developer)
        read = self.call(p.GET, p.AP_PATH.format(viewer.id)).status_code
        written = self.call(p.PUT, p.AP_PATH.format(viewer.id), json={"policy_ids": []}).status_code
        self.assertEqual(
            (unknown, read, written),
            (p.STATUS_NOT_FOUND, p.STATUS_FORBIDDEN, p.STATUS_FORBIDDEN),
            msg=p.MSG_AP_ADMIN_ONLY,
            abort_on_fail=False,
        )
