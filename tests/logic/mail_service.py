"""
* @file     ${tests/logic/mail_service.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests sending Bud's emails.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the delivery, its logs and the structure of every email.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class MailServiceBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_MAIL_CHECK}")

    def bud_sender_name_is_the_product_identity(self):
        self.check("sender")

    def bud_starttls_failure_names_where_and_why(self):
        self.check("starttls")

    def bud_delivery_failure_reaches_the_configuration_handlers(self):
        self.check("handlers")

    def bud_unreachable_relay_is_reported(self):
        self.check("unreachable")

    def bud_delivery_log_leaves_out_message_and_recipient(self):
        self.check("sent log")

    def bud_error_log_leaves_out_the_server_response(self):
        self.check("error log")

    @parameterized(params.MAIL_SENDERS)
    def bud_email_follows_the_product_structure(self, name):
        self.print_variables({"email": name})
        self.check(name)

    def bud_html_values_are_escaped_and_text_values_are_not(self):
        self.check("escaped")

    def bud_request_emails_keep_their_subject_and_next_step(self):
        self.check("requests")
