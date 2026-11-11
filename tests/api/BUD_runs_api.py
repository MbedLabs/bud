"""
* @file     ${tests/api/BUD_runs_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Test runs keep what a station reports and list sorted, filtered and paginated.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests each scenario on a freshly started app.
"""

from datetime import timedelta

from app.models import Runner, TestRun
from tests.api.runs_api import RunsApiBase

SOFTWARE = (
    "test_case_list",
    "name",
    "url_test_software",
    "ref_test_software",
    "url_software_under_test",
    "ref_software_under_test",
)


class RunsApiTest(RunsApiBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.bud.bud_start_app()
        self.bud.bud_add_test_station(with_run=False)
        created = self.bud.bud_station_request(p.POST, p.TEST_RUNS_PATH, json=p.RUNS_CREATED)
        stored = self.bud.bud_find_in_app(TestRun, id=created.json().get("id"))
        expected = {**p.RUNS_CREATED, "name": p.RUNS_CREATED["test_suite_name"]}
        self.tc_created = {
            "status": created.status_code,
            "stored": {
                field: getattr(stored[0], field, None) if stored else None for field in SOFTWARE
            },
            "expected": {field: expected[field] for field in SOFTWARE},
        }
        self.tc_latest = self.latest()
        self.tc_sorted = {field: self.sorted_by(field) for field in p.RUNS_SORT_FIELDS}
        self.tc_pages = self.pages()
        self.tc_display = self.display()
        self.bud.bud_start_app()
        self.tc_invalid = [
            self.bud.bud_request(p.GET, p.TEST_RUNS_PATH, params=query).status_code
            for query in p.RUNS_INVALID_SORTS
        ]

    def add_run(self, name, cases, **fields):
        """Store a run."""
        return self.bud.bud_add_to_app(TestRun(name=name, test_case_list=cases, **fields))

    def listing(self, **query):
        """List the runs: the status, the total and the run ids and names."""
        response = self.bud.bud_request(
            self.parameters.GET, self.parameters.TEST_RUNS_PATH, params=query
        )
        body = response.json() if response.status_code == 200 else {}
        runs = body.get("runs", [])
        return (
            response.status_code,
            body.get("total"),
            [run["id"] for run in runs],
            [run["name"] for run in runs],
        )

    def latest(self):
        """An older and a newer run of one suite and a run of another."""
        p = self.parameters
        self.bud.bud_start_app()
        base = p.RUNS_LATEST_BASE
        self.add_run(*p.RUNS_SUITE, status="Completed", created_at=base)
        newest = self.add_run(*p.RUNS_SUITE, status="Failed", created_at=base + timedelta(hours=1))
        other = self.add_run(
            *p.RUNS_OTHER_SUITE, status="Completed", created_at=base + timedelta(minutes=30)
        )
        status, total, ids, _ = self.listing(latest_per_suite="true")
        return {"status": status, "total": total, "ids": ids, "expected": [newest.id, other.id]}

    def sorted_by(self, field):
        """Two runs on two stations sorted by one field both ways, a run missing the field last."""
        p = self.parameters
        self.bud.bud_start_app()
        base = p.RUNS_SORT_BASE
        stations = [
            self.bud.bud_add_to_app(
                Runner(
                    account=account,
                    password_hash="test",
                    token=token,
                    socket_port=port,
                    location=location,
                )
            )
            for account, token, port, location in p.RUNS_SORT_STATIONS
        ]
        high = self.add_run(
            "Zulu",
            "suite",
            status="Running",
            runner_id=stations[0].id,
            duration_seconds=20,
            started_at=base + timedelta(hours=2),
            completed_at=base + timedelta(hours=3),
            created_at=base,
        )
        low = self.add_run(
            "Alpha",
            "suite",
            status="Completed",
            runner_id=stations[1].id,
            duration_seconds=5,
            started_at=base,
            completed_at=base + timedelta(hours=1),
            created_at=base + timedelta(minutes=1),
        )
        missing = None
        if field not in ("name", "status"):
            missing = self.add_run("Missing", "suite", created_at=base + timedelta(hours=4))
        found = {"directions": [], "filters": []}
        for direction, expected in (("asc", [low.id, high.id]), ("desc", [high.id, low.id])):
            status, _, ids, _ = self.listing(sort_by=field, sort_dir=direction)
            found["directions"].append((status, ids, expected + ([missing.id] if missing else [])))
        if field == "runner_account":
            for filters in p.RUNS_STATION_FILTERS:
                status, total, ids, _ = self.listing(sort_by=field, sort_dir="asc", **filters)
                found["filters"].append((status, total, ids, [low.id]))
        return found

    def pages(self):
        """Thirty matching runs stored in reverse name order and one excluded run, in pages of five."""
        p = self.parameters
        self.bud.bud_start_app()
        for index in reversed(range(p.RUNS_MATCHES)):
            self.add_run(f"Match {index:02d}", "suite", status="Completed")
        self.add_run("Excluded", "suite", status="Running")
        found = {}
        for offset in p.RUNS_PAGES:
            status, total, _, names = self.listing(
                q="Match",
                status="Completed",
                sort_by="name",
                sort_dir="asc",
                limit=p.RUNS_PAGE_SIZE,
                offset=offset,
            )
            found[offset] = (status, total, names)
        return found

    def display(self):
        """Two runs of one suite and one of another, sorted by duration and by name."""
        p = self.parameters
        self.bud.bud_start_app()
        base = p.RUNS_DISPLAY_BASE
        older = self.add_run("Nightly", "suite", created_at=base, duration_seconds=100)
        newer = self.add_run(
            "Nightly", "suite", created_at=base + timedelta(hours=1), duration_seconds=5
        )
        other = self.add_run(
            "Smoke", "suite", created_at=base + timedelta(minutes=30), duration_seconds=10
        )
        found = {"latest": [], "ties": []}
        for direction, expected in (("asc", [newer.id, other.id]), ("desc", [other.id, newer.id])):
            status, total, ids, _ = self.listing(
                latest_per_suite=True, sort_by="duration_seconds", sort_dir=direction
            )
            found["latest"].append((status, total, ids, expected))
        for direction, expected in (("asc", [older.id, newer.id]), ("desc", [newer.id, older.id])):
            found["ties"].append(
                (self.listing(q="Nightly", sort_by="name", sort_dir=direction)[2], expected)
            )
        return found

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RunsApiTest().run()
