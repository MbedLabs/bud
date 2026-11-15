"""
* @file     ${tests/pg/BUD_integration_real_auth_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Real sign-in, real station enrolment and database-backed writes work end to end on PostgreSQL.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests the live app with the seeded administrator and stations enrolled through its API.
"""

from app.core.config import settings
from tests.pg.integration_real_auth_pg import IntegrationRealAuthPgBase


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


class IntegrationRealAuthPgTest(IntegrationRealAuthPgBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.client = client = self.bud.bud_start_live_app()
        ready = client.get("/api/ready")
        wrong = client.post(p.LOGIN_PATH, json={"email": settings.ADMIN_EMAIL, "password": "definitely-the-wrong-password"})
        client.cookies.clear()
        self.tc_checks = {
            "ready": {
                "the probe answers": (ready.status_code, p.STATUS_OK),
                "the database is connected": (body_of(ready).get("database"), "connected"),
            },
            "wrong password": {"a wrong password is refused": (wrong.status_code, p.STATUS_UNAUTHORIZED)},
            "signed out": {
                "a signed-out write is refused": (client.post("/api/products", json={"name": "should-not-persist"}).status_code, p.STATUS_UNAUTHORIZED)
            },
        }
        self.write()
        self.skipped()
        self.producer()

    def write(self):
        p = self.parameters
        login, admin = self.bud.bud_live_bearer()
        created = self.client.post(
            "/api/products", json={"name": self.bud.bud_unique("Integration Widget"), "description": "created via real JWT"}, headers=admin
        )
        listed = self.client.get("/api/products", headers=admin)
        rows = body_of(listed) if isinstance(body_of(listed), list) else []
        self.tc_checks["write"] = {
            "the administrator signs in": (login, p.STATUS_OK),
            "the product is created": (created.status_code, p.STATUS_CREATED),
            "the products are listed": (listed.status_code, p.STATUS_OK),
            "the new product is listed": (any(row.get("id") == body_of(created).get("id") for row in rows), True),
        }

    def skipped(self):
        p = self.parameters
        login, admin = self.bud.bud_live_bearer()
        steps, station = self.bud.bud_live_station()
        results = [
            {"test_class": "Suite.Boots", "test_method": "Boots", "passed": True, "duration_seconds": 1},
            {"test_class": "Suite.Flashes", "test_method": "Flashes", "passed": True, "duration_seconds": 0, "metadata": {"skipped": True}},
            {"test_class": "Suite.Fails", "test_method": "Fails", "passed": False, "duration_seconds": 1},
        ]
        uploaded = self.client.post("/api/results", json={"test_suite_name": self.bud.bud_unique("Robot"), "results": results}, headers=station)
        run = body_of(self.client.get(f"{p.TEST_RUNS_PATH}/{body_of(uploaded).get('test_run_id')}", headers=admin))
        self.tc_checks["skipped"] = {
            "the administrator signs in": (login, p.STATUS_OK),
            "the station is enrolled": (steps, p.PG_ENROLMENT),
            "the results are stored": (uploaded.status_code in (200, 201), True),
            "the counts include one skipped case": (
                (run.get("total_tests"), run.get("passed_tests"), run.get("failed_tests"), run.get("skipped_tests")),
                (3, 1, 1, 1),
            ),
        }

    def producer(self):
        p = self.parameters
        login, human = self.bud.bud_live_bearer()
        steps, station = self.bud.bud_live_station()
        payload = {"test_suite_name": self.bud.bud_unique("Producer"), "test_case_list": "Suite"}
        created = self.client.post(p.TEST_RUNS_PATH, json=payload, headers=station)
        run_id = body_of(created).get("id")
        results = {"results": [{"test_class": "Suite", "test_method": "test_one", "passed": True}]}
        checks = {
            "the administrator signs in": (login, p.STATUS_OK),
            "the station is enrolled": (steps, p.PG_ENROLMENT),
            "the station creates a run": (created.status_code, p.STATUS_CREATED),
            "a person cannot create a run": (self.client.post(p.TEST_RUNS_PATH, json=payload, headers=human).status_code, p.STATUS_FORBIDDEN),
            "a person cannot update a run": (
                self.client.patch(f"{p.TEST_RUNS_PATH}/{run_id}", json={"total_tests": 99}, headers=human).status_code,
                p.STATUS_FORBIDDEN,
            ),
            "a person cannot upload results": (self.client.post("/api/results", json=results, headers=human).status_code, p.STATUS_FORBIDDEN),
        }
        results["test_run_id"] = run_id
        checks["a person cannot upload results to the run"] = (self.client.post("/api/results", json=results, headers=human).status_code, p.STATUS_FORBIDDEN)
        run = body_of(self.client.get(f"{p.TEST_RUNS_PATH}/{run_id}", headers=human))
        checks["the run counts nothing"] = (run.get("total_tests"), 0)
        checks["the run is still running"] = (run.get("status"), "Running")
        checks["the station uploads its results"] = (self.client.post("/api/results", json=results, headers=station).status_code, p.STATUS_CREATED)
        self.tc_checks["producer"] = checks

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    IntegrationRealAuthPgTest().run()
