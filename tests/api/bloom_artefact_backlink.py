"""
* @file     ${tests/api/bloom_artefact_backlink.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the Bloom suite a run points back at.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of the suite reference and the stored backlink.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase

BACKLINK_FIELDS = tuple(params.BLOOM_BACKLINK)


class BloomArtefactBacklinkBase(BudAppTestCase):

    @parameterized(params.BLOOM_REFERENCE_CASES)
    def bud_suite_is_the_reference(self, case):
        self.assertEqual(
            self.tc_references[case],
            self.parameters.BLOOM_SUITE,
            msg=self.parameters.MSG_BLOOM_REFERENCE,
        )

    @parameterized(params.BLOOM_NO_REFERENCE_CASES)
    def bud_no_suite_is_the_reference(self, case):
        self.print_variables({"case": case, "reference": self.tc_references[case]})
        self.assertEqual(
            type(self.tc_references[case]).__name__,
            self.parameters.NONE_TYPE,
            msg=self.parameters.MSG_BLOOM_NO_REFERENCE,
        )

    @parameterized(BACKLINK_FIELDS)
    def bud_sync_stores_the_suite(self, field):
        self.assertEqual(
            getattr(self.tc_named_run, field, None),
            self.parameters.BLOOM_BACKLINK[field],
            msg=self.parameters.MSG_BLOOM_STORED,
        )

    @parameterized(BACKLINK_FIELDS)
    def bud_reply_without_suite_leaves_the_run_unmarked(self, field):
        self.print_variables({field: getattr(self.tc_unnamed_run, field, None)})
        self.assertEqual(
            type(getattr(self.tc_unnamed_run, field, None)).__name__,
            self.parameters.NONE_TYPE,
            msg=self.parameters.MSG_BLOOM_UNMARKED,
        )

    def bud_run_is_read(self):
        self.print_variables({"status": self.tc_exposed.status_code, "body": self.tc_exposed.text})
        self.assertEqual(
            self.tc_exposed.status_code,
            self.parameters.STATUS_OK,
            msg=self.parameters.MSG_BLOOM_RUN_READ,
            abort_on_fail=True,
        )

    @parameterized(BACKLINK_FIELDS)
    def bud_run_endpoint_shows_the_backlink(self, field):
        self.assertEqual(
            self.tc_exposed.json().get(field),
            self.parameters.BLOOM_BACKLINK[field],
            msg=self.parameters.MSG_BLOOM_EXPOSED,
        )
