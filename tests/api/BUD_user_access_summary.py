"""
* @file     ${tests/api/BUD_user_access_summary.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    An Admin reads the products a user can access, by name only.
* @author   Amine El Omari
* @date     2026-11-18
* @version  1.0.0
* @note     This module tests the access summary on a freshly started app.
"""

from app.models import AccessGroup, Product, ProductAccess, User
from tests.api.user_access_summary import UserAccessSummaryBase


class UserAccessSummaryTest(UserAccessSummaryBase):

    def setUpClass(self):
        super().setUpClass()
        p, bud = self.parameters, self.bud
        bud.bud_start_app()
        self.beta = bud.bud_add_to_app(Product(name=p.UAS_BETA))
        self.alpha = bud.bud_add_to_app(Product(name=p.UAS_ALPHA))
        bud.bud_add_to_app(Product(name=p.UAS_GAMMA))
        group_a = bud.bud_add_to_app(AccessGroup(name=p.UAS_GROUP_A))
        group_b = bud.bud_add_to_app(AccessGroup(name=p.UAS_GROUP_B))
        self.member = bud.bud_add_to_app(User(**p.UAS_MEMBER))
        self.newcomer = bud.bud_add_to_app(User(**p.UAS_NEWCOMER))
        for product, group in ((self.beta, group_a), (self.alpha, group_a), (self.alpha, group_b)):
            bud.bud_add_to_app(
                ProductAccess(product_id=product.id, user_id=self.member.id, group_id=group.id)
            )

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    UserAccessSummaryTest().run()
