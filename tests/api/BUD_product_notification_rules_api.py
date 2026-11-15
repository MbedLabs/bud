"""
* @file     ${tests/api/BUD_product_notification_rules_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Administrators and holders of products.manage on a product edit that product's notification rules;
*           a channel takes every product unless switched off.
* @author   Amine El Omari
* @date     2026-11-14
* @version  1.0.0
* @note     This module tests each scenario on a freshly started app with its own encryption key.
"""

from unittest import mock

from cryptography.fernet import Fernet

from app.core.config import settings
from app.models import AccessGroup, AuditEvent, Policy, Product, ProductAccess, ProductNotificationRule, User
from tests.api.product_notification_rules_api import ProductNotificationRulesApiBase


class ProductNotificationRulesApiTest(ProductNotificationRulesApiBase):

    def setUpClass(self):
        super().setUpClass()
        p, bud = self.parameters, self.bud
        self.key = mock.patch.object(settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode())
        self.key.start()
        bud.bud_start_app()
        self.tc_checks = {}
        product_a = bud.bud_add_to_app(Product(name=p.PNR_PRODUCT_A))
        product_b = bud.bud_add_to_app(Product(name=p.PNR_PRODUCT_B))
        every = self.add_channel(p.PNR_EVERY_CHANNEL)
        routed = self.add_channel(p.PNR_ROUTED_CHANNEL, all_products=False)
        patched = bud.bud_request(p.PATCH, p.CHANNEL_PATH.format(every.json()["id"]), json={"all_products": False})
        bud.bud_request(p.PATCH, p.CHANNEL_PATH.format(every.json()["id"]), json={"all_products": True})
        self.tc_checks["all products"] = {
            p.MSG_PNR_ALL_PRODUCTS_DEFAULT: (every.json().get("all_products"), True),
            p.MSG_PNR_ALL_PRODUCTS_OFF: (routed.json().get("all_products"), False),
            p.MSG_PNR_ALL_PRODUCTS_PATCH: (patched.json().get("all_products"), False),
        }
        every_id, routed_id = every.json()["id"], routed.json()["id"]

        created = self.add_rule(product_a.id, routed_id, p.PNR_FAILURES)
        rules = bud.bud_request(p.GET, p.PNR_RULES_PATH.format(product_a.id)).json()
        self.tc_checks["administrator"] = {
            p.MSG_PNR_CREATED: (created.status_code, p.STATUS_CREATED),
            p.MSG_PNR_DUPLICATE: (self.add_rule(product_a.id, routed_id, p.PNR_ALL).status_code, p.STATUS_BAD_REQUEST),
            p.MSG_PNR_MISSING_CHANNEL: (
                self.add_rule(product_a.id, p.PNR_MISSING_ID, p.PNR_ALL).status_code,
                p.STATUS_NOT_FOUND,
            ),
            p.MSG_PNR_MISSING_PRODUCT: (
                self.add_rule(p.PNR_MISSING_ID, routed_id, p.PNR_ALL).status_code,
                p.STATUS_NOT_FOUND,
            ),
            p.MSG_PNR_MISSING_RULE: (
                bud.bud_request(p.DELETE, p.PNR_RULE_PATH.format(product_a.id, p.PNR_MISSING_ID)).status_code,
                p.STATUS_NOT_FOUND,
            ),
            p.MSG_PNR_LISTED: (
                [(rule["channel_name"], rule["channel_format"], rule["run_filter"]) for rule in rules],
                [(p.PNR_ROUTED_CHANNEL, p.CHANNEL["format"], p.PNR_FAILURES)],
            ),
        }
        options = bud.bud_request(p.GET, p.PNR_CHANNELS_PATH.format(product_a.id))
        self.tc_checks["options"] = {
            p.MSG_PNR_OPTIONS: (
                [channel["name"] for channel in options.json()],
                sorted([p.PNR_EVERY_CHANNEL, p.PNR_ROUTED_CHANNEL]),
            ),
            p.MSG_PNR_OPTIONS_HIDDEN: (
                p.CHANNEL_HOOK in options.text or p.CHANNEL["secret"] in options.text,
                False,
            ),
        }

        manage_group = self.add_group(p.PNR_MANAGE_GROUP, p.PNR_MANAGE_POLICY)
        view_group = self.add_group(p.PNR_VIEW_GROUP, p.PNR_VIEW_POLICY)
        manager = bud.bud_add_to_app(User(**p.PNR_MANAGER))
        viewer = bud.bud_add_to_app(User(**p.PNR_VIEWER))
        bud.bud_add_to_app(ProductAccess(product_id=product_a.id, user_id=manager.id, group_id=manage_group.id))
        bud.bud_add_to_app(ProductAccess(product_id=product_a.id, user_id=viewer.id, group_id=view_group.id))

        bud.bud_sign_in_as(manager)
        rule_id = created.json()["id"]
        listed = bud.bud_request(p.GET, p.PNR_RULES_PATH.format(product_a.id)).status_code
        changed = bud.bud_request(
            p.PATCH, p.PNR_RULE_PATH.format(product_a.id, rule_id), json={"run_filter": p.PNR_ALL}
        )
        added = self.add_rule(product_a.id, every_id, p.PNR_FAILURES)
        removed = bud.bud_request(p.DELETE, p.PNR_RULE_PATH.format(product_a.id, added.json().get("id"))).status_code
        self.tc_checks["manager"] = {
            p.MSG_PNR_MANAGER: (
                (listed, changed.status_code, changed.json().get("run_filter"), added.status_code, removed),
                (p.STATUS_OK, p.STATUS_OK, p.PNR_ALL, p.STATUS_CREATED, p.STATUS_NO_CONTENT),
            ),
        }
        refused = {
            p.MSG_PNR_OTHER_PRODUCT: (
                (
                    bud.bud_request(p.GET, p.PNR_RULES_PATH.format(product_b.id)).status_code,
                    self.add_rule(product_b.id, routed_id, p.PNR_ALL).status_code,
                    bud.bud_request(p.GET, p.PNR_CHANNELS_PATH.format(product_b.id)).status_code,
                ),
                (p.STATUS_FORBIDDEN, p.STATUS_FORBIDDEN, p.STATUS_FORBIDDEN),
            ),
        }
        bud.bud_sign_in_as(viewer)
        refused[p.MSG_PNR_VIEWER] = (
            (
                bud.bud_request(p.GET, p.PNR_RULES_PATH.format(product_a.id)).status_code,
                bud.bud_request(p.GET, p.PNR_CHANNELS_PATH.format(product_a.id)).status_code,
                bud.bud_request(
                    p.PATCH, p.PNR_RULE_PATH.format(product_a.id, rule_id), json={"run_filter": p.PNR_FAILURES}
                ).status_code,
                bud.bud_request(p.DELETE, p.PNR_RULE_PATH.format(product_a.id, rule_id)).status_code,
            ),
            (p.STATUS_FORBIDDEN,) * 4,
        )
        self.tc_checks["refused"] = refused

        events = [
            (event.action, event.product_id)
            for action in (p.PNR_CREATED_ACTION, p.PNR_UPDATED_ACTION, p.PNR_DELETED_ACTION)
            for event in bud.bud_find_in_app(AuditEvent, action=action)
        ]
        self.tc_checks["audit"] = {
            p.MSG_PNR_AUDITED: (
                sorted(events),
                sorted(
                    [
                        (p.PNR_CREATED_ACTION, product_a.id),
                        (p.PNR_CREATED_ACTION, product_a.id),
                        (p.PNR_UPDATED_ACTION, product_a.id),
                        (p.PNR_DELETED_ACTION, product_a.id),
                    ]
                ),
            ),
        }

        bud.bud_sign_in_as(bud.admin)
        self.add_rule(product_b.id, every_id, p.PNR_ALL)
        bud.bud_request(p.DELETE, p.CHANNEL_PATH.format(routed_id))
        bud.bud_request(p.DELETE, p.PNR_PRODUCT_PATH.format(product_b.id))
        self.tc_checks["removal"] = {
            p.MSG_PNR_CHANNEL_DELETED: (len(bud.bud_find_in_app(ProductNotificationRule, channel_id=routed_id)), 0),
            p.MSG_PNR_PRODUCT_DELETED: (
                len(bud.bud_find_in_app(ProductNotificationRule, product_id=product_b.id)),
                0,
            ),
        }

    def add_channel(self, name, **changes):
        """Add a channel named name with the given changes to the example channel."""
        p = self.parameters
        return self.bud.bud_request(p.POST, p.CHANNELS_PATH, json={**p.CHANNEL, "name": name, **changes})

    def add_rule(self, product_id, channel_id, run_filter):
        """Add a rule on the product for the channel."""
        p = self.parameters
        return self.bud.bud_request(
            p.POST, p.PNR_RULES_PATH.format(product_id), json={"channel_id": channel_id, "run_filter": run_filter}
        )

    def add_group(self, name, policy):
        """Store a group bundling one new policy."""
        stored = self.bud.bud_add_to_app(Policy(**policy))
        return self.bud.bud_add_to_app(AccessGroup(name=name, policies=[stored]))

    def tearDownClass(self):
        self.key.stop()
        super().tearDownClass()


if __name__ == "__main__":
    ProductNotificationRulesApiTest().run()
