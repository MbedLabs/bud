"""
* @file     ${tests/api/observability.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests request ids, the metrics endpoint and structured logging.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the observability features.
"""

from tests.bud_test_base import BudAppTestCase


class ObservabilityBase(BudAppTestCase):

    def bud_probe_answers(self):
        self.assertEqual(
            self.tc_health.status_code,
            self.parameters.STATUS_OK,
            msg=self.parameters.MSG_REQUEST_ID_ANSWER,
            abort_on_fail=True,
        )

    def bud_response_carries_a_request_id(self):
        request_id = self.tc_health.headers.get("x-request-id")
        self.print_variables({"request id": request_id})
        self.assertTrue(
            bool(request_id),
            msg=self.parameters.MSG_REQUEST_ID_GENERATED,
            actual=request_id,
            abort_on_fail=True,
        )

    def bud_request_id_is_long_enough(self):
        length = len(self.tc_health.headers.get("x-request-id", ""))
        self.assertTrue(
            length >= self.parameters.REQUEST_ID_MIN_LENGTH,
            msg=self.parameters.MSG_REQUEST_ID_LENGTH,
            expected=f">= {self.parameters.REQUEST_ID_MIN_LENGTH}",
            actual=length,
            abort_on_fail=False,
        )

    def bud_incoming_request_id_is_passed_on(self):
        self.assertEqual(
            self.tc_traced.headers.get("x-request-id"),
            self.parameters.REQUEST_ID_INCOMING,
            msg=self.parameters.MSG_REQUEST_ID_PROPAGATED,
            abort_on_fail=False,
        )

    def bud_metrics_answer(self):
        self.print_variables({"status": self.tc_metrics.status_code})
        self.assertEqual(
            self.tc_metrics.status_code,
            self.parameters.STATUS_OK,
            msg=self.parameters.MSG_METRICS_ANSWER,
            abort_on_fail=True,
        )

    def bud_metrics_are_prometheus_text(self):
        self.assertIn(
            self.parameters.METRICS_TEXT_TYPE,
            self.tc_metrics.headers["content-type"],
            msg=self.parameters.MSG_METRICS_TYPE,
            abort_on_fail=False,
        )

    def bud_metrics_count_the_requests(self):
        self.assertIn(
            self.parameters.METRICS_REQUESTS,
            self.tc_metrics.text,
            msg=self.parameters.MSG_METRICS_REQUESTS,
            abort_on_fail=False,
        )

    def bud_metrics_measure_the_duration(self):
        self.assertIn(
            self.parameters.METRICS_DURATION,
            self.tc_metrics.text,
            msg=self.parameters.MSG_METRICS_DURATION,
            abort_on_fail=False,
        )

    def bud_metrics_name_the_probe_path(self):
        self.assertIn(
            self.parameters.METRICS_HEALTH_PATH,
            self.tc_metrics.text,
            msg=self.parameters.MSG_METRICS_HEALTH,
            abort_on_fail=False,
        )

    def bud_disabled_metrics_are_not_found(self):
        self.assertEqual(
            self.tc_metrics_off.status_code,
            self.parameters.STATUS_NOT_FOUND,
            msg=self.parameters.MSG_METRICS_DISABLED,
            abort_on_fail=False,
        )

    def bud_json_log_carries_the_message(self):
        self.print_variables({"log line": self.tc_log_line})
        self.assertEqual(
            self.tc_log_line.get("message"),
            self.parameters.LOG_RECORD_TEXT,
            msg=self.parameters.MSG_LOG_MESSAGE,
            abort_on_fail=False,
        )

    def bud_json_log_carries_the_level(self):
        self.assertEqual(
            self.tc_log_line.get("level"),
            self.parameters.LOG_RECORD_LEVEL,
            msg=self.parameters.MSG_LOG_LEVEL,
            abort_on_fail=False,
        )

    def bud_json_log_carries_the_logger(self):
        self.assertEqual(
            self.tc_log_line.get("logger"),
            self.parameters.LOG_RECORD_LOGGER,
            msg=self.parameters.MSG_LOG_LOGGER,
            abort_on_fail=False,
        )

    def bud_json_log_carries_the_request_id(self):
        self.assertEqual(
            self.tc_log_line.get("request_id"),
            self.parameters.LOG_REQUEST_ID,
            msg=self.parameters.MSG_LOG_REQUEST_ID,
            abort_on_fail=False,
        )

    def bud_logging_set_up_twice_has_one_handler(self):
        self.print_variables({"root handlers": self.tc_root_handlers})
        self.assertEqual(
            len(self.tc_root_handlers),
            self.parameters.LOG_HANDLERS,
            msg=self.parameters.MSG_LOG_HANDLERS,
            abort_on_fail=False,
        )

    def bud_root_handler_writes_json(self):
        self.assertEqual(
            type(self.tc_root_handlers[0].formatter).__name__,
            self.parameters.LOG_JSON_FORMATTER,
            msg=self.parameters.MSG_LOG_FORMATTER,
            abort_on_fail=False,
        )
