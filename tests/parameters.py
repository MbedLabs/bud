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
from datetime import datetime, timedelta, timezone

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

DOCKERFILE = "Dockerfile"
DOCKERFILE_FROM = "FROM "
DOCKERFILE_UI_BUILD = " AS ui-build"
DOCKERFILE_UI_BUILD_STAGES = 1
DOCKERFILE_BUILD_PLATFORM = "--platform=$BUILDPLATFORM"
MSG_DOCKERFILE_ONE_UI_BUILD = "the Dockerfile has exactly one ui-build stage"
MSG_DOCKERFILE_BUILD_PLATFORM = "the ui-build stage runs on the build platform"

TIMESTAMP_NAIVE = datetime(2026, 9, 27, 12, 34, 56, 789)
TIMESTAMP_AWARE = datetime(2026, 9, 27, 14, 34, 56, tzinfo=timezone(timedelta(hours=2)))
TIMESTAMP_TEXT = "2026-09-27 12:34:56 UTC"
TIMESTAMP_NONE_TEXT = ""
MSG_TIMESTAMP_SECONDS = "a time is written in UTC to the second"
MSG_TIMESTAMP_NONE = "no time is written as an empty text"
MSG_TIMESTAMP_AWARE = "a time with an offset is converted to UTC"

GET = "GET"
POST = "POST"
HEALTH_PATH = "/api/health"
READY_PATH = "/api/ready"
HEALTH_HEALTHY = "healthy"
HEALTH_READY = "ready"
DATABASE_CONNECTED = "connected"
MSG_HEALTH_ANSWERS = "the liveness probe answers"
MSG_HEALTH_HEALTHY = "the liveness probe reports healthy"
MSG_HEALTH_NO_DATABASE = "the liveness probe does not claim a connected database"
MSG_READY_ANSWERS = "the readiness probe answers"
MSG_READY_READY = "the readiness probe reports ready"
MSG_READY_DATABASE = "the readiness probe reports the database connected"

APP_UPLOAD_FOLDER = "uploads"
STATUS_CREATED = 201
UPLOAD_PATH = "/api/uploads/{}"
HTML_REPORT_NAME = "log.html"
HTML_REPORT_CONTENT = b"<html><script>alert(1)</script></html>"
HTML_TYPE = "text/html"
ATTACHMENT_PATTERN = "^attachment;"
HTML_REPORT_FILENAME = 'filename="log.html"'
SANDBOX_POLICY = "sandbox"
NO_SNIFF = "nosniff"
MSG_HTML_ACCEPTED = "a station uploads an HTML report"
MSG_HTML_TYPE = "the uploaded HTML report keeps its content type"
MSG_HTML_DOWNLOADS = "the HTML report downloads"
MSG_HTML_ATTACHMENT = "the HTML report downloads as an attachment"
MSG_HTML_FILENAME = "the download keeps the report's file name"
MSG_HTML_SANDBOX = "a browser that renders the download renders it sandboxed"
MSG_HTML_NOSNIFF = "a browser does not sniff the download's content type"

LOG_CAPTURE_CAPACITY = 100000
INVITE_INFO_PATH = "/api/auth/invite-info"
INVITE_INFO_QUERY_PATH = "/api/auth/invite-info?token={}"
ONE_TIME_TOKEN = "SUPERSECRET-DO-NOT-LOG-0123456789abcdef"
APP_LOGGERS = ("bud", "app")
MSG_TOKEN_REQUEST_LOGGED = "the application's own log records record the request"
MSG_TOKEN_NOT_LOGGED = "a one-time token in the body or the query string never reaches the logs"

REPORT_RESULT_CLASS = "Bench"
REPORT_RESULT_METHOD = "Measures within limit"
REPORT_RESULT_ENTRIES = [
    {"passed": True, "assertion_type": "AssertEqual"},
    {"passed": True, "skipped": True, "assertion_type": "Skip", "message": "no probe"},
    {"passed": True, "info": True, "assertion_type": "Log"},
    {"passed": False, "assertion_type": "AssertIn"},
]
REPORT_ASSERTION_ROWS = [("AssertEqual", True), ("AssertIn", False)]
REPORT_ASSERTION_OUTCOME = (1, 1, 0)
MSG_REPORT_ROWS = "the run report's assertion rows leave out skipped and information entries"
MSG_REPORT_OUTCOME = "the assertion outcome counts one passed and one failed assertion"

NONE_TYPE = "NoneType"
TOKEN_SUBJECT = "user@example.com"
TOKEN_LIFETIME = timedelta(minutes=5)
TOKEN_EXPIRY_CLAIM = "exp"
STATION_TOKEN_ACCOUNT = "station-01"
STATION_TOKEN_TYPE = "runner"
MSG_ACCESS_TOKEN_DECODES = "an access token decodes with the secret key"
MSG_ACCESS_TOKEN_SUBJECT = "an access token keeps its subject"
MSG_ACCESS_TOKEN_EXPIRES = "an access token carries its expiry"
MSG_STATION_TOKEN_DECODES = "a Test Station token decodes with the secret key"
MSG_STATION_TOKEN_SUBJECT = "a Test Station token names its account"
MSG_STATION_TOKEN_TYPE = "a Test Station token is a runner token"

CLOUDRON_MANIFEST = "cloudron/CloudronManifest.json"
CLOUDRON_DESCRIPTION = "cloudron/DESCRIPTION.md"
CLOUDRON_CHANGELOG = "cloudron/CHANGELOG"
PYPROJECT = "pyproject.toml"
CLOUDRON_TITLE = "Bud TMP by EmbedLabs"
CLOUDRON_TAGLINE = "Automated software, hardware and system testing"
CLOUDRON_DESCRIPTION_TEXT = (
    "Bud TMP by EmbedLabs provides test management and execution for automated "
    "software, hardware and system testing.\n\n"
    "Manage Test Stations and execution requests, collect results and artifacts, "
    "generate reports, and publish completed run reports to Bloom PLM. Manage users "
    "and policy groups, customize report branding, and receive run notifications."
)
CLOUDRON_EMBEDDED = "embedded"
CLOUDRON_SELF_HOSTED = "self-hosted"
CLOUDRON_VERSION_SECTION = "[{}]\n"
CLOUDRON_VERSION_HEADER = r"^\[(\d+(?:\.\d+){0,2})[^\]]*\]$"
MSG_CLOUDRON_TITLE = "the Cloudron title is the product name"
MSG_CLOUDRON_TAGLINE = "the Cloudron tagline is the product positioning"
MSG_CLOUDRON_DESCRIPTION = "the Cloudron description is the product positioning"
MSG_CLOUDRON_MANIFEST_EMBEDDED = "the Cloudron manifest does not call the product embedded"
MSG_CLOUDRON_DESCRIPTION_EMBEDDED = "the Cloudron description does not call the product embedded"
MSG_CLOUDRON_SELF_HOSTED = "the Cloudron description does not call the product self-hosted"
MSG_CLOUDRON_VERSION = "the Cloudron package version is the product version"
MSG_CLOUDRON_UPSTREAM = "the Cloudron upstream version is the product version"
MSG_CLOUDRON_SECTION = "the Cloudron changelog has a section for the product version"
MSG_CLOUDRON_HEADER = "the Cloudron changelog opens with a version header"
MSG_CLOUDRON_NEWEST = "the changelog's first version is the product version or a later one"

AUDIT_ACTOR_USER = "user"
AUDIT_OLD_ACTION = "old"
AUDIT_NEW_ACTION = "new"
AUDIT_OLD_AGE = timedelta(days=40)
AUDIT_NEW_AGE = timedelta(days=5)
AUDIT_RETENTION_DAYS = 30
AUDIT_PRUNED = 1
AUDIT_LEFT = ["new"]
MSG_AUDIT_PRUNED = "the prune removes the one event older than the retention"
MSG_AUDIT_LEFT = "the event inside the retention is kept"

RESPONSE_MODEL_PACKAGES = ("app.schemas", "app.api")
RESPONSE_MODEL_SUFFIXES = ("Response", "Summary", "Item", "Entry", "Created")
RESPONSE_MODELS_AT_LEAST = 20
RESPONSE_MODEL_API_PREFIX = "app.api."
RESPONSE_UNMARKED = []
MSG_RESPONSE_SCAN_COUNT = "the scan finds more than 20 response models"
MSG_RESPONSE_SCAN_API = "the scan finds response models declared in app.api"
MSG_RESPONSE_UTC = "every timestamp a response model carries has the UTC serializer"

START_SCRIPT = "docker/start.sh"
SUPERVISORD_CONF = "docker/supervisord.conf"
START_SUPERVISORD = 'exec gosu "$APP_USER" /usr/local/bin/supervisord -c /etc/supervisord.conf'
START_SUPERVISORD_PREFIX = 'exec gosu "$APP_USER" /usr/local/bin/supervisord'
START_SUPERVISORD_TIMES = 1
START_APP_USER = "APP_USER=appuser"
START_FD_LOOP = "for fd in 1 2; do"
START_FD_WRITABLE = 'if ! gosu "$APP_USER" test -w "/proc/self/fd/$fd"; then'
START_FD_CHOWN = 'chown "$APP_UID:$APP_GID" "/proc/self/fd/$fd"'
START_CLOUDRON_BLOCK = 'if [ -n "${CLOUDRON_APP_ORIGIN:-}" ]; then'
START_CLOUDRON_ELSE = "\nelse\n"
START_DATA_CHOWN = 'chown -R "$APP_UID:$APP_GID" /app/data'
START_MIGRATION = 'gosu "$APP_USER" alembic upgrade head'
SUPERVISORD_ROOT = "user=root"
SUPERVISORD_PIDFILE = "pidfile=/run/bud/supervisord.pid"
DOCKERFILE_ROOT_USER = r"(?m)^USER root$"
DOCKERFILE_NGINX_USER = "user appuser;"
DOCKERFILE_NGINX_USER_DROP = "-e '/^[[:space:]]*user[[:space:]]/d'"
MSG_START_LAST = "start.sh ends by replacing the shell with supervisord run as appuser"
MSG_START_ONCE = "start.sh starts supervisord once"
MSG_START_APP_USER = "start.sh runs the app as appuser"
MSG_START_FD_LOOP = "start.sh goes through the container's output descriptors 1 and 2"
MSG_START_FD_WRITABLE = "start.sh checks whether appuser can write each descriptor"
MSG_START_FD_CHOWN = "start.sh gives a descriptor appuser cannot write to appuser"
MSG_START_FD_FIRST = "the descriptors are given to appuser before supervisord starts"
MSG_START_DATA_CHOWN = "on Cloudron start.sh gives every file under /app/data to appuser"
MSG_START_DATA_FIRST = "on Cloudron /app/data is given to appuser before the migration runs"
MSG_SUPERVISORD_ROOT = "supervisord has no root user setting"
MSG_SUPERVISORD_PIDFILE = "supervisord keeps its pid file in the appuser runtime folder"
MSG_DOCKERFILE_ROOT = "the image starts as root"
MSG_DOCKERFILE_NGINX_USER = "the Dockerfile writes no nginx user directive for appuser"
MSG_DOCKERFILE_NGINX_DROP = "the Dockerfile removes the user directive from nginx.conf"

TOKEN_HS256 = {"alg": "HS256", "typ": "JWT"}
TOKEN_HASHES = {"HS256": "sha256", "HS512": "sha512"}
TOKEN_USER_ID = "7"
TOKEN_USER_TYPE = "user"
TOKEN_STATION_TYPE = "runner"
TOKEN_VERSION = 1
TOKEN_VALID_MINUTES = 5
TOKEN_STATION_EXPIRED_MINUTES = -60
TOKEN_STATION_JTI = "abc"
TOKEN_REFUSED_CASES = {
    "expired HS256": ({"alg": "HS256", "typ": "JWT"}, -5),
    "HS512": ({"alg": "HS512", "typ": "JWT"}, 5),
    "none": ({"alg": "none", "typ": "JWT"}, 5),
}
MSG_TOKEN_HS256 = "a standard HS256 token decodes"
MSG_TOKEN_ISSUED = "a token Bud issues decodes"
MSG_TOKEN_REFUSED = "an expired token or a token with another algorithm does not decode"
MSG_TOKEN_STATION_EXPIRED = "an expired Test Station token does not decode with the expiry check"
MSG_TOKEN_STATION_NO_CHECK = "an expired Test Station token decodes without the expiry check"
