"""
* @file     ${tests/sec/BUD_run_producer_http.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Only the station that owns a test run writes its records; no person does.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests each role's four run writes on a fresh app and a station's own run.
"""

from datetime import datetime, timezone

from app.models import Runner, TestRun, TestRunEvent
from app.models.user import UserRole
from tests.sec.run_producer_http import RunProducerHttpBase


class RunProducerHttpTest(RunProducerHttpBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_human = {}
        for role in UserRole:
            for operation in self.parameters.RUN_WRITE_OPERATIONS:
                self.tc_human[f"{role.value}, {operation}"] = self.human_write(role, operation)
        self.bud.bud_start_app()
        station = self.bud.bud_add_test_station(with_run=False)
        self.tc_station_id = station.id
        self.tc_created = self.bud.bud_station_request(
            self.parameters.POST,
            self.parameters.TEST_RUNS_PATH,
            json=self.parameters.PRODUCER_STATION_RUN,
        )
        run_id = self.tc_created.json().get("id")
        self.tc_updated = self.bud.bud_station_request(
            self.parameters.PATCH,
            self.parameters.TEST_RUN_PATH.format(run_id),
            json=self.parameters.PRODUCER_STATION_COUNTS,
        )
        self.tc_station_run = (self.bud.bud_find_in_app(TestRun, id=run_id) or [None])[0]

    def human_write(self, role, operation):
        """One run write by a person of the role on a fresh app, and the run state after it."""
        p = self.parameters
        self.bud.bud_start_app()
        self.bud.admin.role = role
        station = self.bud.bud_add_to_app(
            Runner(
                account=p.TEST_STATION_ACCOUNT,
                password_hash=p.TEST_STATION_PASSWORD_HASH,
                token=p.TEST_STATION_TOKEN,
                socket_port=p.TEST_STATION_PORT,
            )
        )
        run = self.bud.bud_add_to_app(
            TestRun(
                name=p.PRODUCER_RUN_NAME,
                test_case_list=p.PRODUCER_CASE_LIST,
                status=p.RUN_RUNNING,
                runner_id=station.id,
                started_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        if operation == "create":
            response = self.bud.bud_request(p.POST, p.TEST_RUNS_PATH, json=p.PRODUCER_HUMAN_RUN)
        elif operation == "patch":
            response = self.bud.bud_request(
                p.PATCH, p.TEST_RUN_PATH.format(run.id), json=p.PRODUCER_HUMAN_PATCH
            )
        else:
            payload = dict(p.PRODUCER_HUMAN_RESULTS)
            if operation == "results-update":
                payload["test_run_id"] = run.id
            response = self.bud.bud_request(p.POST, p.RESULTS_PATH, json=payload)
        after = self.bud.bud_find_in_app(TestRun, id=run.id)[0]
        return {
            "status code": response.status_code,
            "body": response.text,
            "run status": after.status,
            "total tests": after.total_tests,
            "completed at": after.completed_at,
            "runs": len(self.bud.bud_find_in_app(TestRun)),
            "run events": len(self.bud.bud_find_in_app(TestRunEvent)),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RunProducerHttpTest().run()
