"""
* @file     ${tests/api/notification_channels_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the notification channels API.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of the write-only, encrypted channel settings.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class NotificationChannelsApiBase(BudAppTestCase):

    def bud_channel_is_added(self):
        self.print_variables({"status": self.tc_created.status_code, "body": self.tc_created.text})
        self.assertEqual(
            self.tc_created.status_code,
            self.parameters.STATUS_CREATED,
            msg=self.parameters.MSG_CHANNEL_CREATED,
            abort_on_fail=True,
        )

    def bud_answer_hides_url_and_secret(self):
        p = self.parameters
        body = self.tc_created.json()
        self.assertEqual(
            body.get("url_prefix"),
            p.CHANNEL_HOOK[: p.CHANNEL_PREFIX_LENGTH] + p.CHANNEL_PREFIX_ELLIPSIS,
            msg=p.MSG_CHANNEL_PREFIX,
            abort_on_fail=False,
        )
        self.assertEqual(
            body.get("has_secret"), True, msg=p.MSG_CHANNEL_HAS_SECRET, abort_on_fail=False
        )
        self.assertNotIn(p.CHANNEL_URL_FIELD, body, msg=p.MSG_CHANNEL_NO_URL, abort_on_fail=False)
        self.assertNotIn(
            p.CHANNEL_SECRET_FIELD, body, msg=p.MSG_CHANNEL_NO_SECRET, abort_on_fail=False
        )
        self.assertNotIn(
            p.CHANNEL_HOOK, self.tc_created.text, msg=p.MSG_CHANNEL_HOOK_HIDDEN, abort_on_fail=False
        )

    def bud_list_hides_url_and_secret(self):
        p = self.parameters
        self.print_variables({"status": self.tc_listed.status_code, "body": self.tc_listed.text})
        self.assertEqual(
            self.tc_listed.status_code, p.STATUS_OK, msg=p.MSG_CHANNEL_LISTED, abort_on_fail=False
        )
        self.assertNotIn(
            p.CHANNEL_HOOK, self.tc_listed.text, msg=p.MSG_CHANNEL_LIST_HOOK, abort_on_fail=False
        )
        self.assertNotIn(
            p.CHANNEL_SECRET,
            self.tc_listed.text,
            msg=p.MSG_CHANNEL_LIST_SECRET,
            abort_on_fail=False,
        )

    def bud_url_and_secret_are_stored_encrypted(self):
        p = self.parameters
        self.print_variables(
            {"url": self.tc_stored.url_encrypted, "secret": self.tc_stored.secret_encrypted}
        )
        self.assertNotIn(
            p.CHANNEL_HOOK,
            self.tc_stored.url_encrypted,
            msg=p.MSG_CHANNEL_URL_ENCRYPTED,
            abort_on_fail=False,
        )
        self.assertNotIn(
            p.CHANNEL_SECRET,
            self.tc_stored.secret_encrypted,
            msg=p.MSG_CHANNEL_SECRET_ENCRYPTED,
            abort_on_fail=False,
        )

    def bud_change_keeps_the_url_and_clears_the_secret(self):
        p = self.parameters
        self.print_variables({"status": self.tc_patched.status_code, "body": self.tc_patched.text})
        self.assertEqual(
            self.tc_patched.status_code, p.STATUS_OK, msg=p.MSG_CHANNEL_PATCHED, abort_on_fail=True
        )
        self.assertEqual(
            self.tc_patched.json().get("run_filter"),
            p.CHANNEL_PATCHED_FILTER,
            msg=p.MSG_CHANNEL_FILTER,
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_patched.json().get("has_secret"),
            False,
            msg=p.MSG_CHANNEL_SECRET_CLEARED,
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_url_after, self.tc_url_before, msg=p.MSG_CHANNEL_URL_KEPT, abort_on_fail=False
        )

    @parameterized(params.CHANNEL_INVALID)
    def bud_invalid_channel_is_refused(self, case):
        self.print_variables({"case": case, "status": self.tc_invalid[case]})
        self.assertEqual(
            self.tc_invalid[case],
            self.parameters.STATUS_UNPROCESSABLE,
            msg=self.parameters.MSG_CHANNEL_INVALID,
            abort_on_fail=False,
        )

    def bud_duplicate_name_is_refused(self):
        p = self.parameters
        self.print_variables({"first": self.tc_valid, "second": self.tc_duplicate})
        self.assertEqual(
            self.tc_valid, p.STATUS_CREATED, msg=p.MSG_CHANNEL_VALID, abort_on_fail=False
        )
        self.assertEqual(
            self.tc_duplicate,
            p.STATUS_BAD_REQUEST,
            msg=p.MSG_CHANNEL_DUPLICATE,
            abort_on_fail=False,
        )

    def bud_deleted_and_missing_channels(self):
        p = self.parameters
        self.print_variables(
            {"delete": self.tc_deleted, "again": self.tc_deleted_again, "missing": self.tc_missing}
        )
        self.assertEqual(
            self.tc_deleted, p.STATUS_NO_CONTENT, msg=p.MSG_CHANNEL_DELETED, abort_on_fail=False
        )
        self.assertEqual(
            self.tc_deleted_again,
            p.STATUS_NOT_FOUND,
            msg=p.MSG_CHANNEL_DELETED_AGAIN,
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_missing, p.STATUS_NOT_FOUND, msg=p.MSG_CHANNEL_MISSING, abort_on_fail=False
        )

    def bud_test_message_is_delivered(self):
        p = self.parameters
        self.print_variables({"status": self.tc_test.status_code, "body": self.tc_test.text})
        self.assertEqual(
            self.tc_test.status_code, p.STATUS_OK, msg=p.MSG_CHANNEL_TEST_SENT, abort_on_fail=True
        )
        self.assertEqual(
            self.tc_test.json(),
            p.CHANNEL_TEST_RESULT,
            msg=p.MSG_CHANNEL_TEST_RESULT,
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_posted, [p.CHANNEL_HOOK], msg=p.MSG_CHANNEL_TEST_URL, abort_on_fail=False
        )

    def bud_signed_out_visitor_cannot_list_channels(self):
        self.assertEqual(
            self.tc_signed_out,
            self.parameters.STATUS_UNAUTHORIZED,
            msg=self.parameters.MSG_CHANNEL_SIGNED_OUT,
            abort_on_fail=False,
        )
