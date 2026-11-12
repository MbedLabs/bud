"""
* @file     ${tests/sec/BUD_run_authorization.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Test Stations reach their own runs only; signed-out visitors, viewers and developers are refused writes.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests every request on a fresh app database holding one running run of each of two Test Stations.
"""

from datetime import datetime

from app.models import Runner, TestResult, TestRun, TestRunEvent
from app.models.user import User, UserRole
from tests.sec.run_authorization import RunAuthorizationBase


class RunAuthorizationTest(RunAuthorizationBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.tc_cross_create = self.as_station(p.POST, p.TEST_RUNS_PATH, p.RUN_AUTH_CROSS_CREATE)
        self.tc_lists = {sort_by: self.listed(sort_by) for sort_by in p.RUN_AUTH_LIST_SORTS}
        self.tc_foreign = {
            operation: self.as_station(method, path, body, foreign=True)
            for operation, (method, path, body) in p.RUN_AUTH_FOREIGN.items()
        }
        self.tc_signed_out = {
            read: self.signed_out(path) for read, path in p.RUN_AUTH_SIGNED_OUT.items()
        }
        self.tc_viewer = {
            operation: self.as_person(p.RUN_AUTH_VIEWER, request)
            for operation, request in p.RUN_AUTH_VIEWER_WRITES.items()
        }
        self.tc_developer = {
            operation: self.as_person(p.RUN_AUTH_DEVELOPER, p.RUN_AUTH_WRITES[operation])
            for operation in p.RUN_AUTH_DEVELOPER_STATUS
        }
        self.tc_viewer_writes = {
            operation: self.as_person(p.RUN_AUTH_VIEWER_WRITER, p.RUN_AUTH_WRITES[operation])
            for operation in p.RUN_AUTH_VIEWER_REFUSALS
        }

    def seed(self, signed_in=True):
        """A fresh app with two Test Stations, a running run of each, and an event and a failed
        result in the second station's run."""
        p = self.parameters
        self.bud.bud_start_app(signed_in=signed_in)
        stations = [
            self.bud.bud_add_to_app(
                Runner(account=account, password_hash="x", token=token, socket_port=port)
            )
            for account, token, port in p.RUN_AUTH_STATIONS
        ]
        runs = [
            self.bud.bud_add_to_app(
                TestRun(
                    name=f"run-{letter}",
                    test_case_list=f"suite-{letter}",
                    status="Running",
                    runner_id=station.id,
                    started_at=datetime.utcnow(),
                )
            )
            for letter, station in zip("ab", stations)
        ]
        self.bud.bud_add_to_app(
            TestRunEvent(
                test_run_id=runs[1].id,
                sequence=1,
                stage="execution",
                status="running",
                title="Run B started",
            )
        )
        result = self.bud.bud_add_to_app(TestResult(test_run_id=runs[1].id, **p.RUN_AUTH_RESULT))
        return stations, runs, result

    def send(self, method, path, body, run_id, name=""):
        """Send one request, the run id filled into its path and body."""
        p = self.parameters
        if body == "file":
            return self.bud.bud_request(method, path, files={"file": p.RUN_AUTH_UPLOAD_FILE})
        if isinstance(body, dict):
            body = {
                key: (
                    run_id
                    if value == p.RUN_AUTH_RUN_ID
                    else value.format(name) if key == "name" else value
                )
                for key, value in body.items()
            }
        return self.bud.bud_request(method, path.format(run_id), json=body)

    def as_station(self, method, path, body, foreign=False):
        """One request as the first Test Station, about the other station's run when foreign."""
        stations, runs, _ = self.seed()
        self.bud.bud_sign_in_as(stations[0], as_person=False, as_uploader=True)
        return self.send(method, path, body, runs[1].id if foreign else runs[0].id)

    def listed(self, sort_by):
        """The run list as the first Test Station, sorted by one column."""
        stations, runs, _ = self.seed()
        self.bud.bud_sign_in_as(stations[0], as_person=False, as_uploader=True)
        response = self.bud.bud_request(
            self.parameters.GET,
            self.parameters.TEST_RUNS_PATH,
            params={"sort_by": sort_by, "sort_dir": "asc"},
        )
        try:
            ids = [run.get("id") for run in response.json().get("runs", [])]
        except ValueError:
            ids = []
        return response.status_code, ids, runs[0].id, runs[1].id

    def signed_out(self, path):
        """One result read without a signed-in entity."""
        _, runs, result = self.seed(signed_in=False)
        target = result.id if "detail" in path else runs[1].id
        return self.bud.bud_request(self.parameters.GET, path.format(target))

    def as_person(self, person, request):
        """One write as a signed-in person, about the first station's run."""
        _, runs, _ = self.seed()
        user = self.bud.bud_add_to_app(
            User(
                id=person["id"],
                email=person["email"],
                full_name=person["full_name"],
                hashed_password="x",
                role=UserRole(person["role"]),
                is_active=True,
            )
        )
        self.bud.bud_sign_in_as(user, as_uploader=True)
        method, path, body = request
        return self.send(method, path, body, runs[0].id, user.email)

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RunAuthorizationTest().run()
