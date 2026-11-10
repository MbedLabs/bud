"""
* @file     ${tests/api/users.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests deleting users.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of DELETE /api/users/{id}.
"""

from tests.bud_test_base import BudAppTestCase


class UsersBase(BudAppTestCase):

    def bud_user_is_deleted(self):
        self.print_variables({"status": self.tc_delete.status_code, "body": self.tc_delete.text})
        self.assertEqual(
            self.tc_delete.status_code,
            self.parameters.STATUS_NO_CONTENT,
            msg=self.parameters.MSG_USER_DELETED,
            abort_on_fail=False,
        )

    def bud_deleted_user_is_gone(self):
        self.assertEqual(
            self.tc_deleted_users, [], msg=self.parameters.MSG_USER_GONE, abort_on_fail=False
        )

    def bud_deleted_user_tokens_are_gone(self):
        self.assertEqual(
            self.tc_deleted_tokens,
            [],
            msg=self.parameters.MSG_USER_TOKENS_GONE,
            abort_on_fail=False,
        )

    def bud_inviter_is_deleted(self):
        self.print_variables(
            {"status": self.tc_inviter_delete.status_code, "body": self.tc_inviter_delete.text}
        )
        self.assertEqual(
            self.tc_inviter_delete.status_code,
            self.parameters.STATUS_NO_CONTENT,
            msg=self.parameters.MSG_INVITER_DELETED,
            abort_on_fail=False,
        )

    def bud_invitee_no_longer_names_the_inviter(self):
        self.print_variables({"invited by": self.tc_invitee.invited_by_user_id})
        self.assertEqual(
            type(self.tc_invitee.invited_by_user_id).__name__,
            self.parameters.NONE_TYPE,
            msg=self.parameters.MSG_INVITER_CLEARED,
            abort_on_fail=False,
        )

    def bud_self_delete_is_refused(self):
        self.print_variables({"status": self.tc_self.status_code, "body": self.tc_self.text})
        self.assertEqual(
            self.tc_self.status_code,
            self.parameters.STATUS_BAD_REQUEST,
            msg=self.parameters.MSG_SELF_DELETE_REFUSED,
            abort_on_fail=False,
        )

    def bud_self_delete_says_why(self):
        self.assertEqual(
            self.tc_self.json().get("detail"),
            self.parameters.USER_SELF_DELETE_DETAIL,
            msg=self.parameters.MSG_SELF_DELETE_DETAIL,
            abort_on_fail=False,
        )

    def bud_missing_user_is_not_found(self):
        self.print_variables({"status": self.tc_missing.status_code, "body": self.tc_missing.text})
        self.assertEqual(
            self.tc_missing.status_code,
            self.parameters.STATUS_NOT_FOUND,
            msg=self.parameters.MSG_MISSING_USER,
            abort_on_fail=False,
        )
