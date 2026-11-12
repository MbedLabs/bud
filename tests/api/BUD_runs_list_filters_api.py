"""
* @file     ${tests/api/BUD_runs_list_filters_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The run search, the location filter and the latest run per suite cover every page of runs.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests the run list on a fresh app database per scenario, with three Test Stations at two locations.
"""

from datetime import datetime, timedelta

from app.models import Runner, TestRun
from tests.api.runs_list_filters_api import RunsListFiltersApiBase


def names(body):
    """The names of the runs of a list answer."""
    return [run.get("name") for run in body.get("runs", [])]


class RunsListFiltersApiTest(RunsListFiltersApiBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_checks = {}
        self.many()
        self.located()
        self.latest()
        self.newest()
        self.paging()
        self.narrowed()

    def stations(self):
        """A fresh app with two Test Stations at Lab A and one at Lab B."""
        self.bud.bud_start_app()
        return {
            account: self.bud.bud_add_to_app(
                Runner(
                    account=account,
                    password_hash="x",
                    token=f"token-{account}",
                    location=location,
                    is_active=True,
                )
            ).id
            for account, location in self.parameters.RUNS_FILTER_STATIONS
        }

    def add_runs(self, station_id, *runs):
        """Store completed runs of one Test Station, each a name, test case list and age."""
        now = datetime.utcnow()
        for name, cases, age in runs:
            self.bud.bud_add_to_app(
                TestRun(
                    name=name,
                    test_case_list=cases,
                    status="Completed",
                    runner_id=station_id,
                    created_at=now - age,
                )
            )

    def listed(self, query):
        """The run list's answer to one query."""
        return self.bud.bud_request(
            self.parameters.GET, self.parameters.TEST_RUNS_PATH, params=query
        ).json()

    def many(self):
        """Thirty nightly runs and one older endurance run at Lab B."""
        p = self.parameters
        ids = self.stations()
        self.add_runs(
            ids["station-01"],
            *[
                (f"Nightly {index:02d}", "SmokeTests", timedelta(minutes=index))
                for index in range(p.RUNS_FILTER_NIGHTLY)
            ],
        )
        self.add_runs(ids["station-02"], (p.RUNS_FILTER_FOUND, "EnduranceTests", timedelta(days=1)))
        body = {case: self.listed(query) for case, query in p.RUNS_FILTER_QUERIES.items()}
        self.tc_checks["search"] = {
            "the first page leaves the run out": (
                p.RUNS_FILTER_FOUND in names(body["first page"]),
                False,
            ),
            "the search finds the run": (names(body["search"]), [p.RUNS_FILTER_FOUND]),
            "the count describes the search": (body["search"].get("total"), 1),
            "the search matches the test case list": (
                names(body["test case list"]),
                [p.RUNS_FILTER_FOUND],
            ),
            "the search matches the station account": (
                names(body["station account"]),
                [p.RUNS_FILTER_FOUND],
            ),
            "the search ignores case": (body["upper case"].get("total"), 1),
            "a term matching nothing finds no run": (body["no match"].get("runs"), []),
            "a term matching nothing counts none": (body["no match"].get("total"), 0),
        }
        self.tc_checks["location pages"] = {
            "the Lab B run is found past the first page": (
                names(body["Lab B"]),
                [p.RUNS_FILTER_FOUND],
            ),
            "Lab B counts one run": (body["Lab B"].get("total"), 1),
            "a location without stations lists no run": (body["Lab Z"].get("runs"), []),
            "a location without stations counts none": (body["Lab Z"].get("total"), 0),
        }

    def located(self):
        """One run at each Test Station."""
        p = self.parameters
        ids = self.stations()
        for minutes, account in enumerate(("station-01", "station-03", "station-02")):
            self.add_runs(ids[account], (f"At {account}", "c", timedelta(minutes=minutes)))
        body = self.listed(p.RUNS_FILTER_LAB_A)
        self.tc_checks["location"] = {
            "the runs of both Lab A stations": (sorted(names(body)), p.RUNS_FILTER_LAB_A_NAMES),
            "Lab A counts two runs": (body.get("total"), 2),
        }

    def latest(self):
        """A suite run twice and another run once."""
        ids = self.stations()
        self.add_runs(
            ids["station-01"],
            ("Repeated", "c", timedelta(hours=2)),
            ("Repeated", "c", timedelta()),
            ("Other", "c", timedelta()),
        )
        body = self.listed(self.parameters.RUNS_FILTER_LATEST)
        self.tc_checks["latest"] = {
            "the repeated suite appears once": (names(body).count("Repeated"), 1),
            "the other suite appears": ("Other" in names(body), True),
            "two suites are counted": (body.get("total"), 2),
        }

    def newest(self):
        """An older and a newer run of one suite."""
        ids = self.stations()
        self.add_runs(
            ids["station-01"],
            ("Repeated", "older", timedelta(hours=2)),
            ("Repeated", "newer", timedelta()),
        )
        body = self.listed(self.parameters.RUNS_FILTER_LATEST)
        self.tc_checks["newest"] = {
            "the newer run is kept": (
                [run.get("test_case_list") for run in body.get("runs", [])],
                ["newer"],
            ),
        }

    def paging(self):
        """Three suites run twice each."""
        ids = self.stations()
        self.add_runs(
            ids["station-01"],
            *[
                (f"Suite {index}", "c", timedelta(minutes=attempt))
                for index in range(3)
                for attempt in range(2)
            ],
        )
        body = self.listed(self.parameters.RUNS_FILTER_LATEST_PAGE)
        self.tc_checks["paging"] = {
            "three suites are counted": (body.get("total"), 3),
            "the page holds two runs": (len(body.get("runs", [])), 2),
        }

    def narrowed(self):
        """One suite run at Lab A and, an hour earlier, at Lab B."""
        ids = self.stations()
        self.add_runs(ids["station-01"], ("Shared", "c", timedelta()))
        self.add_runs(ids["station-02"], ("Shared", "c", timedelta(hours=1)))
        body = self.listed(self.parameters.RUNS_FILTER_LATEST_LAB_B)
        runs = body.get("runs") or [{}]
        self.tc_checks["narrowed"] = {
            "Lab B counts one run": (body.get("total"), 1),
            "the Lab B run is kept": (runs[0].get("runner_account"), "station-02"),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RunsListFiltersApiTest().run()
