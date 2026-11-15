"""
* @file     ${tests/api/BUD_observability.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Requests carry ids, the metrics endpoint serves Prometheus text and logs are JSON lines.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests the whole app's probe and metrics and the logging set-up.
"""

import json
import logging
from unittest import mock

from app.core import observability
from app.core.config import settings
from tests.api.observability import ObservabilityBase


class ObservabilityTest(ObservabilityBase):

    def setUpClass(self):
        super().setUpClass()
        self.bud.bud_start_app()
        self.tc_health = self.bud.bud_request(self.parameters.GET, self.parameters.HEALTH_PATH)
        self.tc_traced = self.bud.bud_request(
            self.parameters.GET,
            self.parameters.HEALTH_PATH,
            headers={self.parameters.REQUEST_ID_HEADER: self.parameters.REQUEST_ID_INCOMING},
        )
        self.bud.bud_request(self.parameters.GET, self.parameters.HEALTH_PATH)
        self.tc_metrics = self.bud.bud_request(self.parameters.GET, self.parameters.METRICS_PATH)
        with mock.patch.object(settings, "ENABLE_METRICS", False):
            self.tc_metrics_off = self.bud.bud_request(
                self.parameters.GET, self.parameters.METRICS_PATH
            )
        token = observability.request_id_var.set(self.parameters.LOG_REQUEST_ID)
        try:
            record = logging.LogRecord(
                name=self.parameters.LOG_RECORD_LOGGER,
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg=self.parameters.LOG_RECORD_MESSAGE,
                args=(self.parameters.LOG_RECORD_ARGUMENT,),
                exc_info=None,
            )
            self.tc_log_line = json.loads(observability.JsonLogFormatter().format(record))
        finally:
            observability.request_id_var.reset(token)
        root = logging.getLogger()
        handlers, level = list(root.handlers), root.level
        observability.setup_logging(level=self.parameters.LOG_RECORD_LEVEL, json_logs=True)
        observability.setup_logging(level=self.parameters.LOG_RECORD_LEVEL, json_logs=True)
        self.tc_root_handlers = list(root.handlers)
        root.handlers[:] = handlers
        root.setLevel(level)

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ObservabilityTest().run()
