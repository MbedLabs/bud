"""
* @file     ${tests/sec/run_authorization.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests who may read and write which test runs.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the Test Station, signed-out, viewer and developer refusals.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class RunAuthorizationBase(BudAppTestCase):

    def bud_station_cannot_create_a_run_for_another_station(self):
        response = self.tc_cross_create
        self.print_variables({"status": response.status_code, "body": response.text})
        self.assertEqual(
            response.status_code,
            self.parameters.STATUS_FORBIDDEN,
            msg=self.parameters.MSG_RUN_AUTH_OTHER_STATION,
        )

    @parameterized(params.RUN_AUTH_LIST_SORTS)
    def bud_station_lists_its_own_runs_only(self, sort_by):
        status, ids, own, other = self.tc_lists[sort_by]
        self.print_variables({"sort_by": sort_by, "status": status, "listed": ids})
        self.assertEqual(status, self.parameters.STATUS_OK, msg=self.parameters.MSG_RUN_AUTH_LIST)
        self.assertIn(own, ids, msg=self.parameters.MSG_RUN_AUTH_LIST)
        self.assertNotIn(other, ids, msg=self.parameters.MSG_RUN_AUTH_LIST)

    @parameterized(params.RUN_AUTH_FOREIGN)
    def bud_station_cannot_reach_another_stations_run(self, operation):
        response = self.tc_foreign[operation]
        self.print_variables(
            {"operation": operation, "status": response.status_code, "body": response.text}
        )
        self.assertIn(
            response.status_code,
            self.parameters.RUN_AUTH_REFUSED,
            msg=f"{operation}: {self.parameters.MSG_RUN_AUTH_FOREIGN}",
        )

    @parameterized(params.RUN_AUTH_SIGNED_OUT)
    def bud_result_reads_need_a_signed_in_entity(self, read):
        response = self.tc_signed_out[read]
        self.print_variables({"read": read, "status": response.status_code, "body": response.text})
        self.assertEqual(
            response.status_code,
            self.parameters.STATUS_UNAUTHORIZED,
            msg=f"{read}: {self.parameters.MSG_RUN_AUTH_SIGNED_OUT}",
        )

    @parameterized(params.RUN_AUTH_VIEWER_WRITES)
    def bud_viewer_is_read_only(self, operation):
        response = self.tc_viewer[operation]
        self.print_variables(
            {"operation": operation, "status": response.status_code, "body": response.text}
        )
        self.assertEqual(
            response.status_code,
            self.parameters.STATUS_FORBIDDEN,
            msg=f"{operation}: {self.parameters.MSG_RUN_AUTH_VIEWER}",
        )

    @parameterized(params.RUN_AUTH_DEVELOPER_STATUS)
    def bud_developer_queues_custom_runs_and_publishes_only(self, operation):
        response = self.tc_developer[operation]
        self.print_variables(
            {"operation": operation, "status": response.status_code, "body": response.text}
        )
        self.assertEqual(
            response.status_code,
            self.parameters.RUN_AUTH_DEVELOPER_STATUS[operation],
            msg=f"{operation}: {self.parameters.MSG_RUN_AUTH_DEVELOPER}",
        )

    @parameterized(params.RUN_AUTH_VIEWER_REFUSALS)
    def bud_viewer_cannot_upload_queue_or_publish(self, operation):
        response = self.tc_viewer_writes[operation]
        self.print_variables(
            {"operation": operation, "status": response.status_code, "body": response.text}
        )
        self.assertEqual(
            response.status_code,
            self.parameters.STATUS_FORBIDDEN,
            msg=f"{operation}: {self.parameters.MSG_RUN_AUTH_VIEWER}",
        )
        self.assertEqual(
            self.detail(response),
            self.parameters.RUN_AUTH_VIEWER_REFUSALS[operation],
            msg=f"{operation}: {self.parameters.MSG_RUN_AUTH_DETAIL}",
        )

    @staticmethod
    def detail(response):
        """The detail of a JSON answer, or its text."""
        try:
            return response.json().get("detail")
        except ValueError:
            return response.text
