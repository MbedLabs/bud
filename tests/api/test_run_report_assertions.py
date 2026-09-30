"""The run report's assertion rows leave out skipped and information entries."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-at-least-32-characters-long")

from app.models import TestResult  # noqa: E402
from app.services.run_reports import _assertion_details, _outcome_for_assertions  # noqa: E402


def test_skipped_and_information_entries_are_not_assertions():
    result = TestResult(
        test_class="Bench",
        test_method="Measures within limit",
        passed=True,
        assertions=[
            {"passed": True, "assertion_type": "AssertEqual"},
            {"passed": True, "skipped": True, "assertion_type": "Skip", "message": "no probe"},
            {"passed": True, "info": True, "assertion_type": "Log"},
            {"passed": False, "assertion_type": "AssertIn"},
        ],
    )

    details = _assertion_details([result])

    assert [(d.assertion_type, d.passed) for d in details] == [("AssertEqual", True), ("AssertIn", False)]
    outcome = _outcome_for_assertions(details)
    assert (outcome.passed, outcome.failed, outcome.skipped) == (1, 1, 0)
