"""
* @file     ${tests/api/user_access_summary.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the summary of the products a user can access.
* @author   Amine El Omari
* @date     2026-11-18
* @version  1.0.0
* @note     Base class containing the bud methods of the user access summary.
"""

from tests.bud_test_base import BudAppTestCase


class UserAccessSummaryBase(BudAppTestCase):

    def bud_the_summary_lists_each_product_once_by_name(self):
        p = self.parameters
        answer = self.bud.bud_request(p.GET, p.UAS_PATH.format(self.member.id))
        self.print_variables({"status": answer.status_code, "summary": answer.json()})
        self.assertEqual(
            (answer.status_code, answer.json()),
            (
                p.STATUS_OK,
                {
                    "every_product": False,
                    "products": [
                        {"product_id": self.alpha.id, "product_name": p.UAS_ALPHA},
                        {"product_id": self.beta.id, "product_name": p.UAS_BETA},
                    ],
                },
            ),
            msg=p.MSG_UAS_SUMMARY,
            abort_on_fail=False,
            method=p.GET,
            endpoint=p.UAS_PATH,
        )
        self.assertNotIn(p.UAS_GROUP_A, answer.text, msg=p.MSG_UAS_NO_GROUPS, abort_on_fail=False)

    def bud_a_user_without_access_has_no_product(self):
        p = self.parameters
        answer = self.bud.bud_request(p.GET, p.UAS_PATH.format(self.newcomer.id))
        self.print_variables({"summary": answer.json()})
        self.assertEqual(
            answer.json(), {"every_product": False, "products": []}, msg=p.MSG_UAS_EMPTY
        )

    def bud_an_administrator_has_every_product(self):
        p = self.parameters
        answer = self.bud.bud_request(p.GET, p.UAS_PATH.format(self.bud.admin.id))
        self.print_variables({"summary": answer.json()})
        self.assertEqual(answer.json()["every_product"], True, msg=p.MSG_UAS_ADMIN)

    def bud_an_unknown_user_is_not_found(self):
        p = self.parameters
        answer = self.bud.bud_request(p.GET, p.UAS_PATH.format(p.UAS_UNKNOWN_ID))
        self.assertEqual(answer.status_code, p.STATUS_NOT_FOUND, msg=p.MSG_UAS_UNKNOWN)

    def bud_the_summary_is_for_administrators_only(self):
        p = self.parameters
        self.bud.bud_sign_in_as(self.member)
        answer = self.bud.bud_request(p.GET, p.UAS_PATH.format(self.member.id))
        self.bud.bud_sign_in_as(self.bud.admin)
        self.assertEqual(answer.status_code, p.STATUS_FORBIDDEN, msg=p.MSG_UAS_ADMIN_ONLY)
