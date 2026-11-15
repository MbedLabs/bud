"""
* @file     ${tests/api/results_listing_payload_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests what a run's result listing carries.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of the listing and the single result.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class ResultsListingPayloadApiBase(BudAppTestCase):

    def bud_station_uploads_a_failed_result(self):
        self.print_variables({"status": self.tc_upload.status_code, "body": self.tc_upload.text})
        self.assertEqual(
            self.tc_upload.status_code,
            self.parameters.STATUS_CREATED,
            msg=self.parameters.MSG_RESULT_UPLOADED,
            abort_on_fail=True,
        )

    def bud_listing_omits_the_method_traceback(self):
        self.print_variables({"rows": self.tc_rows})
        self.assertEqual(
            len(self.tc_rows), self.parameters.RESULT_ROWS, msg=self.parameters.MSG_RESULT_ONE_ROW
        )
        self.assertNotIn(
            self.parameters.RESULT_TRACE_FIELD,
            self.tc_rows[0],
            msg=self.parameters.MSG_RESULT_NO_TRACE,
        )

    @parameterized(params.RESULT_LIST_FIELDS)
    def bud_listing_keeps_the_column(self, field):
        self.assertIn(field, self.tc_rows[0], msg=self.parameters.MSG_RESULT_FIELD)

    def bud_listing_keeps_the_assertion_trace(self):
        self.assertEqual(
            self.tc_rows[0]["assertions"][0].get("traceback"),
            self.parameters.RESULT_ASSERTION_TRACE,
            msg=self.parameters.MSG_RESULT_ASSERTION_TRACE,
        )

    def bud_listing_keeps_the_recorded_order(self):
        self.assertEqual(
            self.tc_order, self.parameters.RESULT_ORDER, msg=self.parameters.MSG_RESULT_ORDER
        )

    def bud_unknown_run_is_not_found(self):
        self.assertEqual(
            self.tc_missing_run,
            self.parameters.STATUS_NOT_FOUND,
            msg=self.parameters.MSG_RESULT_MISSING_RUN,
        )

    def bud_single_result_carries_the_method_traceback(self):
        self.print_variables({"detail": self.tc_detail})
        self.assertEqual(
            self.tc_detail.get("traceback"),
            self.parameters.RESULT_TRACE,
            msg=self.parameters.MSG_RESULT_DETAIL_TRACE,
        )

    def bud_method_traceback_is_stored(self):
        self.assertEqual(
            self.tc_stored_trace,
            self.parameters.RESULT_TRACE,
            msg=self.parameters.MSG_RESULT_STORED_TRACE,
        )
