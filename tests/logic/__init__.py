"""The Bud suites of tests/logic, as bud-runner run-tests -t tests.logic.SUITES runs them."""

import tests.config  # noqa: F401

SUITES = [
    "tests.logic.BUD_dockerfile.DockerfileTest",
    "tests.logic.BUD_timestamp_text.TimestampTextTest",
]
