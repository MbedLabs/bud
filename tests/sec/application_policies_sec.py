"""
* @file     ${tests/sec/application_policies_sec.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests that holding several application policies never widens access.
* @author   Amine El Omari
* @date     2026-11-18
* @version  1.0.0
* @note     Base class containing the bud methods of guarded access management; every person signs in with a real token and each step starts its own app.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from app.core.security import get_password_hash
from app.models import Product
from app.models.access import AccessGroup, Policy, ProductAccess
from app.models.user import User, UserRole
from tests.bud_test_base import BudAppTestCase


class ApplicationPoliciesSecBase(BudAppTestCase):

    def fresh(self):
        """Start the app with no one signed in and return the parameters."""
        self.bud.bud_start_app(signed_in=False)
        self.product = self.bud.bud_add_to_app(Product(name=self.parameters.ASEC_PRODUCT))
        return self.parameters

    def user(self, email, role):
        """Store an active user with the shared password and return its id."""
        return self.bud.bud_add_to_app(
            User(
                email=email,
                full_name=email.split("@")[0],
                hashed_password=get_password_hash(self.parameters.ASEC_PASSWORD),
                role=role,
                is_active=True,
            )
        ).id

    def policy_ids(self, *keys):
        """The ids of the shipped policies with these system keys."""
        return [self.bud.bud_find_in_app(Policy, system_key=key)[0].id for key in keys]

    def group(self, name, *policy_keys):
        """The id of the group of that name, made from the shipped policies when it is custom."""
        existing = self.bud.bud_find_in_app(AccessGroup, name=name)
        if existing:
            return existing[0].id
        policies = [self.bud.bud_find_in_app(Policy, system_key=key)[0] for key in policy_keys]
        return self.bud.bud_add_to_app(AccessGroup(name=name, policies=policies)).id

    def hold(self, user_id, *keys):
        """Store the shipped policies with these keys as the user's application policies."""
        for policy_id in self.policy_ids(*keys):
            self.bud.bud_run_sql(
                "INSERT INTO user_application_policies (user_id, policy_id) VALUES (:u, :p)",
                u=user_id,
                p=policy_id,
            )

    def rows(self, user_id):
        """How many application policies the user holds."""
        return self.bud.bud_run_sql(
            "SELECT count(*) FROM user_application_policies WHERE user_id = :u", u=user_id
        )[0]

    def product_rows(self, user_id):
        """How many groups the user holds on the product."""
        return self.bud.bud_run_sql(
            "SELECT count(*) FROM product_access WHERE user_id = :u AND product_id = :p",
            u=user_id,
            p=self.product.id,
        )[0]

    def login(self, email):
        """Sign in with the shared password and return the status and the bearer header."""
        response = self.bud.bud_request(
            self.parameters.POST,
            self.parameters.LOGIN_PATH,
            json={"email": email, "password": self.parameters.ASEC_PASSWORD},
        )
        return response.status_code, {
            "Authorization": f"Bearer {response.json().get('access_token')}"
        }

    def set_policies(self, user_id, policy_ids, headers):
        """Set a user's application policies as the signed-in person."""
        return self.bud.bud_request(
            self.parameters.PUT,
            self.parameters.ASEC_AP_PATH.format(user_id),
            json={"policy_ids": policy_ids},
            headers=headers,
        )

    def give_on_product(self, group_id, user_id, headers):
        """Give a group to a user on the product as the signed-in person."""
        return self.bud.bud_request(
            self.parameters.PUT,
            self.parameters.ASEC_PRODUCT_GROUP_PATH.format(self.product.id, group_id),
            json={"user_ids": [user_id]},
            headers=headers,
        )

    def bud_policies_without_access_management_open_nothing(self):
        p = self.fresh()
        member = self.user("member@example.com", UserRole.viewer)
        target = self.user("target@example.com", UserRole.viewer)
        self.hold(member, *p.ASEC_SPREAD_KEYS)
        login, headers = self.login("member@example.com")
        found = {
            "login": login,
            "groups": self.bud.bud_request(p.GET, p.GROUPS_PATH, headers=headers).status_code,
            "users": self.bud.bud_request(p.GET, p.ACCESS_USERS_PATH, headers=headers).status_code,
            "set": self.set_policies(target, self.policy_ids(p.ASEC_AUDIT), headers).status_code,
            "give": self.give_on_product(self.group(p.ASEC_OPERATORS), target, headers).status_code,
            "rows": (self.rows(target), self.product_rows(target)),
        }
        self.print_variables(found)
        self.assertEqual(found["login"], p.STATUS_OK, msg=p.MSG_ASEC_SIGNED_IN)
        self.assertEqual(found["groups"], p.STATUS_FORBIDDEN, msg=p.MSG_ASEC_GROUPS_CLOSED)
        self.assertEqual(found["users"], p.STATUS_FORBIDDEN, msg=p.MSG_ASEC_USERS_CLOSED)
        self.assertEqual(found["set"], p.STATUS_FORBIDDEN, msg=p.MSG_ASEC_SET_CLOSED)
        self.assertEqual(found["give"], p.STATUS_FORBIDDEN, msg=p.MSG_ASEC_GIVE_CLOSED)
        self.assertEqual(found["rows"], (0, 0), msg=p.MSG_ASEC_NO_ROW)

    def bud_every_policy_still_cannot_reach_administration(self):
        p = self.fresh()
        giver = self.user("giver@example.com", UserRole.developer)
        holder = self.user("holder@example.com", UserRole.developer)
        recipient = self.user("recipient@example.com", UserRole.developer)
        self.hold(giver, *p.ASEC_EVERY_APP_KEY)
        self.bud.bud_add_to_app(
            ProductAccess(
                product_id=self.product.id, user_id=giver, group_id=self.group(p.ASEC_OPERATORS)
            )
        )
        self.hold(holder, p.ASEC_AUDIT)
        login, headers = self.login("giver@example.com")
        administrators = self.group(p.ASEC_ADMIN_GROUP)
        given = self.give_on_product(administrators, recipient, headers)
        found = {
            "login": login,
            "given": (given.status_code, given.json().get("detail")),
            "set": self.set_policies(recipient, self.policy_ids(p.ASEC_AUDIT), headers).status_code,
            "removed": self.set_policies(holder, [], headers).status_code,
            "recipient rows": (self.rows(recipient), self.product_rows(recipient)),
            "holder rows": self.rows(holder),
        }
        self.print_variables(found)
        self.assertEqual(found["login"], p.STATUS_OK, msg=p.MSG_ASEC_SIGNED_IN)
        self.assertEqual(
            found["given"], (p.STATUS_FORBIDDEN, p.ASEC_ADMIN_ONLY), msg=p.MSG_ASEC_ADMIN_GIVE
        )
        self.assertEqual(found["set"], p.STATUS_FORBIDDEN, msg=p.MSG_ASEC_SET_ADMIN_ONLY)
        self.assertEqual(found["removed"], p.STATUS_FORBIDDEN, msg=p.MSG_ASEC_REMOVE_ADMIN_ONLY)
        self.assertEqual(found["recipient rows"], (0, 0), msg=p.MSG_ASEC_NO_ROW)
        self.assertEqual(found["holder rows"], 1, msg=p.MSG_ASEC_HOLDER_KEPT)

    @parameterized(params.ASEC_MANAGEMENT_KEYS)
    def bud_viewer_is_refused_management(self, key):
        p = self.fresh()
        self.user("boss@example.com", UserRole.admin)
        viewer = self.user("member@example.com", UserRole.viewer)
        self.hold(viewer, *p.ASEC_SPREAD_KEYS)
        login, headers = self.login("boss@example.com")
        held = self.policy_ids(*p.ASEC_SPREAD_KEYS)
        answer = self.set_policies(viewer, held + self.policy_ids(key), headers)
        self.print_variables({"answer": answer.status_code, "rows": self.rows(viewer)})
        self.assertEqual(login, p.STATUS_OK, msg=p.MSG_ASEC_SIGNED_IN)
        self.assertEqual(answer.status_code, p.STATUS_UNPROCESSABLE, msg=p.MSG_ASEC_VIEWER_REFUSED)
        self.assertEqual(self.rows(viewer), len(held), msg=p.MSG_ASEC_VIEWER_ROWS)

    def bud_spread_access_does_not_cover_a_third_policy(self):
        p = self.fresh()
        giver = self.user("giver@example.com", UserRole.developer)
        recipient = self.user("recipient@example.com", UserRole.developer)
        self.hold(giver, *p.ASEC_GIVER_KEYS)
        covered, wider = self.group(*p.ASEC_COVERED), self.group(*p.ASEC_WIDER)
        login, headers = self.login("giver@example.com")
        found = {
            "login": login,
            "wider": self.give_on_product(wider, recipient, headers).status_code,
            "covered": self.give_on_product(covered, recipient, headers).status_code,
            "rows": self.product_rows(recipient),
        }
        self.print_variables(found)
        self.assertEqual(found["login"], p.STATUS_OK, msg=p.MSG_ASEC_SIGNED_IN)
        self.assertEqual(found["wider"], p.STATUS_FORBIDDEN, msg=p.MSG_ASEC_WIDER_REFUSED)
        self.assertEqual(found["covered"], p.STATUS_OK, msg=p.MSG_ASEC_COVERED_GIVEN)
        self.assertEqual(found["rows"], 1, msg=p.MSG_ASEC_ONE_ROW)
