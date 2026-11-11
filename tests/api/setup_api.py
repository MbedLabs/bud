"""
* @file     ${tests/api/setup_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the first-run setup.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of the setup status and the first administrator.
"""

from tests.bud_test_base import BudAppTestCase


class SetupApiBase(BudAppTestCase):

    def bud_empty_instance_needs_setup(self):
        self.print_variables({"status": self.tc_empty.status_code, "body": self.tc_empty.text})
        self.assertEqual(
            self.tc_empty.status_code,
            self.parameters.STATUS_OK,
            msg=self.parameters.MSG_SETUP_STATUS_ANSWERS,
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_empty.json(),
            self.parameters.SETUP_REQUIRED,
            msg=self.parameters.MSG_SETUP_REQUIRED,
            abort_on_fail=False,
        )

    def bud_seeded_instance_needs_no_setup(self):
        self.print_variables({"status": self.tc_seeded.status_code, "body": self.tc_seeded.text})
        self.assertEqual(
            self.tc_seeded.status_code,
            self.parameters.STATUS_OK,
            msg=self.parameters.MSG_SETUP_STATUS_ANSWERS,
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_seeded.json(),
            self.parameters.SETUP_DONE,
            msg=self.parameters.MSG_SETUP_DONE_SEEDED,
            abort_on_fail=False,
        )

    def bud_setup_creates_an_active_administrator(self):
        self.print_variables({"status": self.tc_created.status_code, "body": self.tc_created.text})
        self.assertEqual(
            self.tc_created.status_code,
            self.parameters.STATUS_CREATED,
            msg=self.parameters.MSG_SETUP_CREATED,
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_admin.role.value,
            self.parameters.SETUP_ADMIN_ROLE,
            msg=self.parameters.MSG_SETUP_ADMIN_ROLE,
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_admin.is_active,
            True,
            msg=self.parameters.MSG_SETUP_ADMIN_ACTIVE,
            abort_on_fail=False,
        )
        self.assertNotEqual(
            self.tc_admin.hashed_password,
            self.parameters.SETUP_PASSWORD,
            msg=self.parameters.MSG_SETUP_PASSWORD_HASHED,
            abort_on_fail=False,
        )

    def bud_setup_closes_the_window(self):
        self.assertEqual(
            self.tc_after_setup,
            self.parameters.SETUP_DONE,
            msg=self.parameters.MSG_SETUP_DONE,
            abort_on_fail=False,
        )
        self.print_variables({"second setup": self.tc_second.status_code, "users": self.tc_users})
        self.assertEqual(
            self.tc_second.status_code,
            self.parameters.STATUS_CONFLICT,
            msg=self.parameters.MSG_SETUP_SECOND_REFUSED,
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_users, self.parameters.SETUP_USERS, msg=self.parameters.MSG_SETUP_ONE_USER
        )

    def bud_setup_refuses_a_short_password(self):
        self.assertEqual(
            self.tc_short.status_code,
            self.parameters.STATUS_UNPROCESSABLE,
            msg=self.parameters.MSG_SETUP_SHORT_PASSWORD,
            abort_on_fail=False,
        )

    def bud_setup_returns_no_secret(self):
        self.print_variables({"body": self.tc_quiet_body})
        self.assertNotIn(
            self.parameters.SETUP_RUNNER_KEY,
            self.tc_quiet_body,
            msg=self.parameters.MSG_SETUP_NO_SECRET,
            abort_on_fail=False,
        )
        self.assertTrue(
            bool(self.tc_quiet_body.get("message")),
            msg=self.parameters.MSG_SETUP_MESSAGE,
            actual=self.tc_quiet_body.get("message"),
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_after_quiet,
            self.parameters.SETUP_DONE,
            msg=self.parameters.MSG_SETUP_DONE,
            abort_on_fail=False,
        )

    def bud_setup_succeeds_without_mail(self):
        self.print_variables({"status": self.tc_no_mail.status_code, "body": self.tc_no_mail.text})
        self.assertEqual(
            self.tc_no_mail.status_code,
            self.parameters.STATUS_CREATED,
            msg=self.parameters.MSG_SETUP_WITHOUT_MAIL,
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_after_no_mail,
            self.parameters.SETUP_DONE,
            msg=self.parameters.MSG_SETUP_DONE,
            abort_on_fail=False,
        )

    def bud_setup_emails_the_new_administrator(self):
        self.print_variables({"welcome email": self.tc_sent})
        self.assertEqual(
            self.tc_sent.get("to_email"),
            self.parameters.SETUP_OWNER["email"],
            msg=self.parameters.MSG_SETUP_MAIL_TO,
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_sent.get("full_name"),
            self.parameters.SETUP_OWNER["full_name"],
            msg=self.parameters.MSG_SETUP_MAIL_NAME,
            abort_on_fail=False,
        )
        self.assertRegex(
            self.tc_sent.get("login_link", ""),
            f"{self.parameters.SETUP_LOGIN_SUFFIX}$",
            msg=self.parameters.MSG_SETUP_MAIL_LINK,
            abort_on_fail=False,
        )
