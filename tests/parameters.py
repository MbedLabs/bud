"""
* @file     ${tests/parameters.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Constants of Bud's tests: drawn test data, expected values and messages.
* @author   Amine El Omari
* @date     2026-11-07
* @version  1.0.0
* @note     Test data is drawn from SEED; BUDTEST_SEED repeats a run with the same data.
"""

import os
import random
import string
from datetime import datetime, timedelta

SEED = int(os.environ.get("BUDTEST_SEED") or random.SystemRandom().randrange(1, 10**9))
_draw = random.Random(SEED)


def _letters(alphabet: str, low: int, high: int) -> str:
    """A drawn word of ``low`` to ``high`` letters from ``alphabet``."""
    return "".join(_draw.choices(alphabet, k=_draw.randint(low, high)))


def _name() -> str:
    """A drawn capitalised name."""
    return _letters(string.ascii_uppercase, 1, 1) + _letters(string.ascii_lowercase, 4, 8)


DATABASE = "sqlite+aiosqlite:///:memory:"
API_BASE = "http://bud.test"
TEST_RUNS_PREFIX = "/api/test-runs"
STATS_PATH = "/stats"
STATUS_OK = 200
RUN_COMPLETED = "Completed"

ADMIN_ID = _draw.randrange(1, 1000)
ADMIN_EMAIL = f"{_letters(string.ascii_lowercase, 5, 8)}@example.com"
STATION_ACCOUNT = f"station-{_letters(string.ascii_lowercase, 4, 8)}"
STATION_PASSWORD_HASH = _letters(string.ascii_letters, 16, 32)
STATION_TOKEN = _letters(string.ascii_letters + string.digits, 24, 32)

PASSED = "passed"
FAILED = "failed"
SKIPPED = "skipped"
SUITE = _name()
OTHER_SUITE = SUITE + _name()
LATEST_PASSED = _draw.randint(1, 4)
LATEST_FAILED = _draw.randint(1, 4)
LATEST_SKIPPED = _draw.randint(1, 4)
DISTINCT_TESTS = LATEST_PASSED + LATEST_FAILED + LATEST_SKIPPED
TEST_CLASSES = [f"{_name()}{index}Tests" for index in range(DISTINCT_TESTS)]
LATEST_OUTCOMES = _draw.sample(
    [PASSED] * LATEST_PASSED + [FAILED] * LATEST_FAILED + [SKIPPED] * LATEST_SKIPPED,
    DISTINCT_TESTS,
)
EARLIER_OUTCOME = {PASSED: FAILED, FAILED: PASSED, SKIPPED: PASSED}
EARLIER_OUTCOMES = [EARLIER_OUTCOME[outcome] for outcome in LATEST_OUTCOMES]
RUN_COUNT = _draw.randint(2, 5)
METHODS_PER_CLASS = _draw.randint(1, 3)
OTHER_SUITE_CLASSES = [f"{_name()}{index}OtherTests" for index in range(_draw.randint(1, 3))]
FIRST_RUN_AT = datetime(2025, 1, 1) + timedelta(minutes=_draw.randrange(0, 365 * 24 * 60))
RUN_SPACING = timedelta(minutes=_draw.randint(1, 60))
DISTINCT_PASS_RATE = round(LATEST_PASSED / DISTINCT_TESTS * 100, 1)
TEST_EXECUTIONS = RUN_COUNT * DISTINCT_TESTS

MSG_STATS_ANSWER = "the run statistics answer"
MSG_DISTINCT_ONCE = "each test of the suite is counted once however often it ran"
MSG_DISTINCT_LATEST = (
    "each distinct test takes the outcome of its latest run, ties to the newer run"
)
MSG_DISTINCT_RATE = "the distinct test pass rate is passed distinct tests out of all of them"
MSG_EXECUTIONS = "test executions count every test of every run"
MSG_SUITE_FILTER = "without a suite filter the other suite's tests are counted too"

WORK_DIR_SETTING = "BUDTEST_WORK_DIR"
APP_DATABASE_FOLDER = "bud-app"
APP_DATABASE_FILE = "test.db"
TEST_ADMIN_ID = 1
TEST_ADMIN_EMAIL = "tester@example.com"
TEST_ADMIN_NAME = "Tester"
TEST_ADMIN_PASSWORD_HASH = "not-used"
TEST_STATION_ACCOUNT = "station-01"
TEST_STATION_PASSWORD_HASH = "x"
TEST_STATION_TOKEN = "station-token"
TEST_STATION_PORT = 53035
TEST_STATION_RUN = "station-run"
EMPTY_TEST_LIST = "[]"
RUN_RUNNING = "Running"
UPLOADS_PATH = "/api/uploads"
