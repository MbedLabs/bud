"""The Bud suites of tests/sec, as bud-runner run-tests -t tests.sec.SUITES runs them."""

import tests.config  # noqa: F401

SUITES = [
    "tests.sec.BUD_token_logging.TokenLoggingTest",
    "tests.sec.BUD_security.SecurityTest",
]
