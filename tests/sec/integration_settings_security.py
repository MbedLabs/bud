"""
* @file     ${tests/sec/integration_settings_security.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the Bloom integration credentials.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the write-only, encrypted Bloom token.
"""

from tests.bud_test_base import BudAppTestCase


class IntegrationSettingsSecurityBase(BudAppTestCase):

    def bud_token_is_saved(self):
        self.print_variables({"status": self.tc_saved.status_code, "body": self.tc_saved.text})
        self.assertEqual(
            self.tc_saved.status_code,
            self.parameters.STATUS_OK,
            msg=self.parameters.MSG_PLM_SAVED,
            abort_on_fail=True,
        )

    def bud_answer_says_a_token_is_saved(self):
        self.assertEqual(
            self.tc_saved.json()["has_bloom_token"],
            True,
            msg=self.parameters.MSG_PLM_HAS_TOKEN,
            abort_on_fail=False,
        )

    def bud_answer_shows_only_the_token_prefix(self):
        self.assertEqual(
            self.tc_saved.json()["bloom_token_prefix"],
            self.parameters.BLOOM_TOKEN[: self.parameters.BLOOM_TOKEN_PREFIX_LENGTH],
            msg=self.parameters.MSG_PLM_PREFIX,
            abort_on_fail=False,
        )

    def bud_answer_has_no_token_field(self):
        self.assertNotIn(
            self.parameters.BLOOM_TOKEN_FIELD,
            self.tc_saved.json(),
            msg=self.parameters.MSG_PLM_NO_TOKEN_FIELD,
            abort_on_fail=False,
        )

    def bud_token_is_stored_encrypted(self):
        self.print_variables({"stored": [row.value for row in self.tc_stored]})
        self.assertEqual(
            len(self.tc_stored), 1, msg=self.parameters.MSG_PLM_STORED, abort_on_fail=True
        )
        self.assertNotIn(
            self.parameters.BLOOM_TOKEN,
            self.tc_stored[0].value,
            msg=self.parameters.MSG_PLM_ENCRYPTED,
            abort_on_fail=False,
        )

    def bud_reading_never_shows_the_token(self):
        self.print_variables({"read": self.tc_read.text})
        self.assertNotIn(
            self.parameters.BLOOM_TOKEN,
            self.tc_read.text,
            msg=self.parameters.MSG_PLM_GET_NO_TOKEN,
            abort_on_fail=False,
        )
        self.assertNotIn(
            self.parameters.BLOOM_TOKEN_FIELD,
            self.tc_read.json(),
            msg=self.parameters.MSG_PLM_GET_NO_FIELD,
            abort_on_fail=False,
        )

    def bud_new_origin_with_masked_token_is_refused(self):
        self.print_variables(
            {"status": self.tc_new_origin.status_code, "body": self.tc_new_origin.text}
        )
        self.assertEqual(
            self.tc_new_origin.status_code,
            self.parameters.STATUS_UNPROCESSABLE,
            msg=self.parameters.MSG_PLM_ORIGIN_REFUSED,
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_new_origin_after,
            self.tc_new_origin_before,
            msg=self.parameters.MSG_PLM_ORIGIN_KEPT,
            abort_on_fail=False,
        )

    def bud_same_origin_keeps_the_token(self):
        self.print_variables(
            {"status": self.tc_same_origin.status_code, "body": self.tc_same_origin.text}
        )
        self.assertEqual(
            self.tc_same_origin.status_code,
            self.parameters.STATUS_OK,
            msg=self.parameters.MSG_PLM_SAME_ORIGIN,
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_same_origin_after,
            self.tc_same_origin_before,
            msg=self.parameters.MSG_PLM_SAME_ORIGIN_KEPT,
            abort_on_fail=False,
        )

    def bud_invalid_port_is_refused(self):
        self.print_variables(
            {"status": self.tc_bad_port.status_code, "body": self.tc_bad_port.text}
        )
        self.assertEqual(
            self.tc_bad_port.status_code,
            self.parameters.STATUS_UNPROCESSABLE,
            msg=self.parameters.MSG_PLM_INVALID_PORT,
            abort_on_fail=False,
        )

    def bud_generic_settings_do_not_reach_the_secret(self):
        self.print_variables(
            {"read": self.tc_generic_read.status_code, "write": self.tc_generic_write.status_code}
        )
        self.assertEqual(
            self.tc_generic_read.status_code,
            self.parameters.STATUS_NOT_FOUND,
            msg=self.parameters.MSG_SETTING_SECRET_READ,
            abort_on_fail=False,
        )
        self.assertEqual(
            self.tc_generic_write.status_code,
            self.parameters.STATUS_FORBIDDEN,
            msg=self.parameters.MSG_SETTING_SECRET_WRITE,
            abort_on_fail=False,
        )
