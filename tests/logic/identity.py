"""
* @file     ${tests/logic/identity.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the fixed product name and identity.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of the identity in settings, emails, API and reports.
"""

from tests.bud_test_base import BudAppTestCase


class IdentityBase(BudAppTestCase):

    def bud_identity_constants(self):
        p = self.parameters
        self.assertEqual(self.tc_name, p.IDENTITY_NAME, msg=p.MSG_IDENTITY_NAME)
        self.assertEqual(self.tc_full, p.IDENTITY_FULL, msg=p.MSG_IDENTITY_FULL)

    def bud_environment_variable_does_not_rename_the_product(self):
        p = self.parameters
        mail = self.tc_invite
        self.print_variables({"subject": mail.get("subject"), "text": mail.get("text_body")})
        self.assertEqual(self.tc_env_has_name, False, msg=p.MSG_IDENTITY_NO_SETTING)
        self.assertEqual(mail.get("subject"), p.IDENTITY_INVITE_SUBJECT, msg=p.MSG_IDENTITY_SUBJECT)
        self.assertIn(p.IDENTITY_HTML_TITLE, mail.get("html_body", ""), msg=p.MSG_IDENTITY_TITLE)
        self.assertIn(
            p.IDENTITY_INVITE_HEADING, mail.get("html_body", ""), msg=p.MSG_IDENTITY_HEADING
        )
        self.assertIn(p.IDENTITY_INVITE_TEXT, mail.get("text_body", ""), msg=p.MSG_IDENTITY_TEXT)
        self.assertNotIn(
            p.IDENTITY_OVERRIDE,
            mail.get("html_body", "") + mail.get("text_body", ""),
            msg=p.MSG_IDENTITY_NO_OVERRIDE,
        )

    def bud_dotenv_entry_does_not_rename_the_product(self):
        p = self.parameters
        self.assertEqual(
            self.tc_dotenv_uploads, p.IDENTITY_DOTENV_UPLOADS, msg=p.MSG_IDENTITY_DOTENV_READ
        )
        self.assertEqual(self.tc_dotenv_has_name, False, msg=p.MSG_IDENTITY_NO_SETTING)

    def bud_every_email_names_the_product(self):
        p = self.parameters
        self.assertEqual(
            [mail.get("subject") for mail in self.tc_requests],
            p.IDENTITY_SUBJECTS,
            msg=p.MSG_IDENTITY_SUBJECT,
        )
        for mail in self.tc_requests:
            self.assertIn(
                p.IDENTITY_HTML_TITLE, mail.get("html_body", ""), msg=p.MSG_IDENTITY_TITLE
            )
            self.assertIn(p.IDENTITY_HEADING, mail.get("html_body", ""), msg=p.MSG_IDENTITY_HEADING)
            self.assertIn(p.IDENTITY_NAME, mail.get("text_body", ""), msg=p.MSG_IDENTITY_TEXT)
        self.assertIn(
            p.IDENTITY_REPORT_TEXT,
            self.tc_requests[-1].get("text_body", ""),
            msg=p.MSG_IDENTITY_TEXT,
        )

    def bud_api_title_and_root_message_are_the_identity(self):
        p = self.parameters
        self.assertEqual(self.tc_api_title, p.IDENTITY_FULL, msg=p.MSG_IDENTITY_API_TITLE)
        self.assertEqual(self.tc_root_message, p.IDENTITY_FULL, msg=p.MSG_IDENTITY_ROOT)

    def bud_app_keeps_its_identity_with_the_old_variable_set(self):
        p = self.parameters
        result = self.tc_process
        self.print_variables({"stderr": result.stderr})
        self.assertEqual(result.returncode, 0, msg=p.MSG_IDENTITY_PROCESS)
        lines = [
            line
            for line in result.stdout.splitlines()
            if line.startswith(p.IDENTITY_PROCESS_PREFIX)
        ]
        self.assertEqual(lines, p.IDENTITY_PROCESS_LINES, msg=p.MSG_IDENTITY_PROCESS_LINES)

    def bud_every_html_template_titles_itself_with_the_identity(self):
        p = self.parameters
        self.assertEqual(
            len(self.tc_html_templates), p.IDENTITY_TEMPLATES, msg=p.MSG_IDENTITY_TEMPLATE_COUNT
        )
        untitled = [
            name
            for name, text in self.tc_html_templates.items()
            if p.IDENTITY_TEMPLATE_TITLE not in text
        ]
        self.assertEqual(untitled, [], msg=p.MSG_IDENTITY_TEMPLATE_TITLE)

    def bud_no_template_spells_the_product_name(self):
        self.assertEqual(self.tc_spelled, [], msg=self.parameters.MSG_IDENTITY_TEMPLATE_SPELLED)

    def bud_notifications_name_the_product(self):
        p = self.parameters
        self.assertEqual(self.tc_open_in, p.IDENTITY_OPEN_IN, msg=p.MSG_IDENTITY_OPEN_IN)
        self.assertEqual(self.tc_sample, p.IDENTITY_SAMPLE, msg=p.MSG_IDENTITY_SAMPLE)

    def bud_pdf_report_names_the_product(self):
        p = self.parameters
        self.assertEqual(self.tc_pdf_author, p.IDENTITY_FULL, msg=p.MSG_IDENTITY_PDF_AUTHOR)
        for text in p.IDENTITY_PDF_TEXTS:
            self.assertIn(text, self.tc_pdf_text, msg=p.MSG_IDENTITY_PDF_TEXT)

    def bud_summary_report_title_names_the_product(self):
        self.assertEqual(
            self.tc_summary_title,
            self.parameters.IDENTITY_SUMMARY_TITLE,
            msg=self.parameters.MSG_IDENTITY_SUMMARY,
        )

    def bud_web_app_manifest_names_the_product(self):
        self.assertEqual(
            self.tc_manifest_names,
            self.parameters.IDENTITY_MANIFEST_NAMES,
            msg=self.parameters.MSG_IDENTITY_MANIFEST,
        )
