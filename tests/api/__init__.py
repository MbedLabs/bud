"""The Bud suites of tests/api, as bud-runner run-tests -t tests.api.SUITES runs them."""

import tests.config  # noqa: F401

SUITES = [
    "tests.api.BUD_run_stats_distinct.RunStatsDistinctTest",
]
