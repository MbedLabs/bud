"""The Bud suites of tests/api, as bud-runner run-tests -t tests.api.SUITES runs them."""

import tests.config  # noqa: F401

SUITES = [
    "tests.api.BUD_run_stats_distinct.RunStatsDistinctTest",
    "tests.api.BUD_health.HealthTest",
    "tests.api.BUD_html_artifacts.HtmlArtifactsTest",
    "tests.api.BUD_run_report_assertions.RunReportAssertionsTest",
    "tests.api.BUD_observability.ObservabilityTest",
]
