"""
* @file     ${tests/api/BUD_product_access_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A user reads the runs of the products where he holds a group; administrators set a product's members.
* @author   Amine El Omari
* @date     2026-11-13
* @version  1.0.0
* @note     This module tests each scenario on a freshly started app.
"""

from app.models import AccessGroup, AuditEvent, Policy, Product, ProductAccess, TestRun, User
from tests.api.product_access_api import ProductAccessApiBase


class ProductAccessApiTest(ProductAccessApiBase):

    def setUpClass(self):
        super().setUpClass()
        p, bud = self.parameters, self.bud
        bud.bud_start_app()
        product_a = bud.bud_add_to_app(Product(name=p.PA_PRODUCT_A))
        product_b = bud.bud_add_to_app(Product(name=p.PA_PRODUCT_B))
        run_a = self.add_run(p.PA_RUN_A, product_a.id)
        run_b = self.add_run(p.PA_RUN_B, product_b.id)
        run_none = self.add_run(p.PA_RUN_NONE, None)
        view_group = self.add_group(p.PA_VIEW_GROUP, p.PA_VIEW_POLICY)
        manage_group = self.add_group(p.PA_MANAGE_GROUP, p.PA_MANAGE_POLICY)
        viewer = bud.bud_add_to_app(User(**p.PA_VIEWER))
        manager = bud.bud_add_to_app(User(**p.PA_MANAGER))
        newcomer = bud.bud_add_to_app(User(**p.PA_NEWCOMER))
        bud.bud_add_to_app(
            ProductAccess(product_id=product_a.id, user_id=viewer.id, group_id=view_group.id)
        )
        bud.bud_add_to_app(
            ProductAccess(product_id=product_a.id, user_id=manager.id, group_id=manage_group.id)
        )

        self.tc_admin_no_product_run = bud.bud_request(
            p.GET, p.PA_RUN_PATH.format(run_none.id)
        ).status_code
        path = p.PA_GROUP_MEMBERS_PATH.format(product_b.id, view_group.id)
        answer = bud.bud_request(p.PUT, path, json={"user_ids": [newcomer.id]})
        self.tc_set_status = answer.status_code
        self.tc_set_members = [member["email"] for member in answer.json()]
        self.tc_added_events = len(bud.bud_find_in_app(AuditEvent, action=p.PA_ADDED_ACTION))
        bud.bud_request(p.PUT, path, json={"user_ids": []})
        self.tc_cleared_members = bud.bud_request(
            p.GET, p.PA_MEMBERS_PATH.format(product_b.id)
        ).json()
        self.tc_removed_events = len(bud.bud_find_in_app(AuditEvent, action=p.PA_REMOVED_ACTION))

        bud.bud_sign_in_as(viewer)
        self.tc_listed = [run["name"] for run in bud.bud_request(p.GET, p.PA_RUNS_PATH).json()["runs"]]
        self.tc_stats_runs = bud.bud_request(p.GET, p.PA_STATS_PATH).json().get("total_runs")
        self.tc_own_run = bud.bud_request(p.GET, p.PA_RUN_PATH.format(run_a.id)).status_code
        self.tc_other_run = bud.bud_request(p.GET, p.PA_RUN_PATH.format(run_b.id)).status_code
        self.tc_no_product_run = bud.bud_request(
            p.GET, p.PA_RUN_PATH.format(run_none.id)
        ).status_code
        self.tc_me_permissions = bud.bud_request(p.GET, p.PA_ME_PATH).json().get("permissions", [])
        self.tc_viewer_set = bud.bud_request(p.PUT, path, json={"user_ids": [viewer.id]}).status_code

        bud.bud_sign_in_as(manager)
        self.tc_manage_own = bud.bud_request(
            p.PATCH, p.PA_PRODUCT_PATH.format(product_a.id), json=p.PA_RENAME
        ).status_code
        self.tc_manage_other = bud.bud_request(
            p.PATCH, p.PA_PRODUCT_PATH.format(product_b.id), json=p.PA_RENAME
        ).status_code
        self.tc_manage_create = bud.bud_request(
            p.POST, p.PA_PRODUCTS_PATH, json={"name": p.PA_RUN_LIST}
        ).status_code

    def add_run(self, name, product_id):
        """Store a completed run of the product, or of none."""
        p = self.parameters
        return self.bud.bud_add_to_app(
            TestRun(
                name=name,
                test_case_list=p.PA_RUN_LIST,
                status=p.PA_RUN_STATUS,
                product_id=product_id,
            )
        )

    def add_group(self, name, policy):
        """Store a group bundling one new policy."""
        stored = self.bud.bud_add_to_app(Policy(**policy))
        return self.bud.bud_add_to_app(AccessGroup(name=name, policies=[stored]))

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ProductAccessApiTest().run()
