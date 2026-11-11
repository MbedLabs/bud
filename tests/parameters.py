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

METRICS_PATH = "/api/metrics"
REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_MIN_LENGTH = 16
REQUEST_ID_INCOMING = "trace-me-123"
METRICS_TEXT_TYPE = "text/plain"
METRICS_REQUESTS = "http_requests_total"
METRICS_DURATION = "http_request_duration_seconds"
METRICS_HEALTH_PATH = 'path="/health"'
STATUS_NOT_FOUND = 404
LOG_RECORD_LOGGER = "bud.test"
LOG_RECORD_MESSAGE = "hello %s"
LOG_RECORD_ARGUMENT = "world"
LOG_RECORD_TEXT = "hello world"
LOG_RECORD_LEVEL = "INFO"
LOG_REQUEST_ID = "req-abc"
LOG_HANDLERS = 1
LOG_JSON_FORMATTER = "JsonLogFormatter"
MSG_REQUEST_ID_ANSWER = "the liveness probe answers"
MSG_REQUEST_ID_GENERATED = "the response carries a generated request id"
MSG_REQUEST_ID_LENGTH = "a generated request id has at least 16 characters"
MSG_REQUEST_ID_PROPAGATED = "an incoming request id is passed on in the response"
MSG_METRICS_ANSWER = "the metrics endpoint answers"
MSG_METRICS_TYPE = "the metrics are in the Prometheus text format"
MSG_METRICS_REQUESTS = "the metrics count the requests"
MSG_METRICS_DURATION = "the metrics measure the request duration"
MSG_METRICS_HEALTH = "the metrics name the probe's path"
MSG_METRICS_DISABLED = "disabled metrics are not found"
MSG_LOG_MESSAGE = "a JSON log line carries the formatted message"
MSG_LOG_LEVEL = "a JSON log line carries the level"
MSG_LOG_LOGGER = "a JSON log line carries the logger"
MSG_LOG_REQUEST_ID = "a JSON log line carries the request id"
MSG_LOG_HANDLERS = "setting up logging twice leaves one root handler"
MSG_LOG_FORMATTER = "the root handler writes JSON"

USER_PATH = "/api/users/{}"
DELETE = "DELETE"
STATUS_NO_CONTENT = 204
STATUS_BAD_REQUEST = 400
USER_HASH = "hash"
USER_DELETED_EMAIL = "to_delete@example.com"
USER_DELETED_NAME = "To Delete"
USER_INVITE_HASH = "some-hash"
USER_INVITE_LIFETIME = timedelta(hours=1)
USER_INVITER_EMAIL = "inviter@example.com"
USER_INVITER_NAME = "Inviter"
USER_INVITEE_EMAIL = "invitee@example.com"
USER_INVITEE_NAME = "Invitee"
USER_MISSING_ID = 9999
USER_SELF_DELETE_DETAIL = "Admin users cannot delete their own account"
MSG_USER_DELETED = "an administrator deletes a user"
MSG_USER_GONE = "the deleted user is gone"
MSG_USER_TOKENS_GONE = "the deleted user's tokens are gone"
MSG_INVITER_DELETED = "an administrator deletes a user who invited another"
MSG_INVITER_CLEARED = "the invited user no longer names the deleted inviter"
MSG_SELF_DELETE_REFUSED = "an administrator cannot delete their own account"
MSG_SELF_DELETE_DETAIL = "the refusal says the administrator cannot delete their own account"
MSG_MISSING_USER = "deleting a user that does not exist is not found"

LOGO_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\xdac\xfc\xcf\xc0P\x0f\x00\x04\x85\x01\x80\x84\xa9"
    b"\x8c!\x00\x00\x00\x00IEND\xaeB`\x82"
)
LOGO_NAME = "logo.png"
LOGO_TYPE = "image/png"
LOGO_NOT_AN_IMAGE = b"nope"
LOGO_TEXT_TYPE = "text/plain"
HTTP_EXCEPTION = "HTTPException"
STATUS_UNSUPPORTED_MEDIA = 415
PDF_MAGIC = b"%PDF-"
PDF_FORMAT = "pdf"
REPORT_TITLE = "Bud Test Report"
REPORT_SUBTITLE = "Test outcomes"
REPORT_FILTERS = [("Window", "Last 7 days")]
REPORT_OVERALL = (9, 1, 2)
REPORT_BREAKDOWN_TITLE = "Per suite"
REPORT_BREAKDOWN_LABEL = "Suite"
REPORT_BREAKDOWN_ROW = "smoke"
REPORT_APP_VERSION = "1.0.0"
REPORT_LOGO_IMAGES = 1
MSG_LOGO_STORED = "an administrator stores a PNG logo"
MSG_LOGO_SERVED = "the stored logo is served"
MSG_LOGO_FOR_REPORTS = "reports load the stored logo"
MSG_LOGO_DELETED = "after the logo is deleted it is not found"
MSG_LOGO_DELETED_STATUS = "a deleted logo answers not found"
MSG_LOGO_DELETED_REPORTS = "after the logo is deleted reports load none"
MSG_LOGO_NOT_IMAGE = "a logo that is not an image is refused"
MSG_LOGO_NOT_IMAGE_STATUS = "a logo that is not an image is an unsupported media type"
MSG_REPORT_PDF = "the report without a logo is a PDF"
MSG_REPORT_LOGO_PDF = "the report with the logo is a PDF"
MSG_REPORT_LOGO_IMAGE = "the report with the logo has exactly one image more"

PASSWORD_VALID = "correct horse battery"
PASSWORD_SHORT = "short"
PASSWORD_CHARACTER = "x"
PASSWORD_MULTIBYTE = "é" * 37
PASSWORD_SHORT_CASES = ("empty", "one character", "one under the minimum")
PASSWORD_TOO_SHORT_TEXT = "at least"
PASSWORD_TOO_LONG_TEXT = "too long"
VALUE_ERROR = "ValueError"
VALIDATION_ERROR = "ValidationError"
PASSWORD_SCHEMAS = {
    "UserCreate": ("password", {"email": "u@example.com", "full_name": "U"}),
    "PasswordChange": ("new_password", {"current_password": "whatever-old"}),
    "AcceptInviteRequest": ("password", {"token": "t"}),
    "ResetPasswordRequest": ("new_password", {"token": "t"}),
}
MSG_PASSWORD_MINIMUM = "a password of the minimum length is accepted"
MSG_PASSWORD_SHORT_REFUSED = "a password under the minimum length is refused"
MSG_PASSWORD_SHORT_TEXT = "the refusal says the password must be at least the minimum length"
MSG_PASSWORD_LONG_REFUSED = "a password over the byte limit is refused"
MSG_PASSWORD_LONG_TEXT = "the refusal says the password is too long"
MSG_PASSWORD_MULTIBYTE_CHARACTERS = "the multibyte password has fewer characters than the byte limit"
MSG_PASSWORD_MULTIBYTE_REFUSED = "a password over the byte limit in two-byte characters is refused"
MSG_PASSWORD_SCHEMA_SHORT = "every request that sets a password refuses a short one"
MSG_PASSWORD_SCHEMA_VALID = "every request that sets a password accepts a valid one"

ALEMBIC_VERSIONS = "alembic/versions"
ALEMBIC_PATTERN = "*.py"
ALEMBIC_PACKAGE_FILE = "__init__.py"
ALEMBIC_HEAD = "009_admin_email_change_workflow"
ALEMBIC_BASELINE = "009_admin_email_change_workflow.py"
ALEMBIC_ROOT_MARKERS = ("down_revision: Union[str, Sequence[str], None] = None", "down_revision = None")
ALEMBIC_TYPED_ROOT = "down_revision: Union[str, Sequence[str], None] = None"
ALEMBIC_PARENT = "down_revision = "
ALEMBIC_NO_PARENT = "down_revision = None"
ALEMBIC_CREATE_ALL = "create_all"
ALEMBIC_REVISION_ID = 'revision: str = "{}"'
ALEMBIC_CREATE_TABLE = "op.create_table("
ALEMBIC_CORE_TABLES = ("users", "test_runs", "test_results", "artifacts")
ALEMBIC_TABLE_NAME = '"{}"'
ALEMBIC_DROP_TYPE = "DROP TYPE IF EXISTS"
MSG_ALEMBIC_ONE_ROOT = "the baseline is the only root of the migration chain"
MSG_ALEMBIC_PARENT = "every later revision names a parent"
MSG_ALEMBIC_NOT_ROOT = "no later revision is a root"
MSG_ALEMBIC_LATER_CREATE_ALL = "no later revision rebuilds the schema from the models"
MSG_ALEMBIC_HEAD_ID = "the baseline keeps the deployed head's revision id"
MSG_ALEMBIC_BASELINE_ROOT = "the baseline has no parent"
MSG_ALEMBIC_NO_CREATE_ALL = "the baseline calls no create_all"
MSG_ALEMBIC_EXPLICIT_DDL = "the baseline creates its tables with explicit DDL"
MSG_ALEMBIC_CORE_TABLE = "the baseline creates the core table"
MSG_ALEMBIC_DROP_TYPE = "the baseline drops its enum types on downgrade"

PUBLIC_ENDPOINTS = (
    "root",
    "health_check",
    "readiness_check",
    "get_version",
    "prometheus_metrics",
    "login",
    "refresh",
    "logout",
    "get_invite_info",
    "accept_invite",
    "verify_email",
    "forgot_password",
    "reset_password",
    "confirm_email_change",
    "register_runner",
    "setup_status",
    "create_first_admin",
    "cli_start",
    "cli_exchange",
    "cli_refresh",
)
AUTH_DEPENDENCIES = frozenset(
    {
        "get_current_active_entity",
        "get_current_runner",
        "get_current_user",
        "get_uploader_entity",
        "require_admin",
        "require_runner_api_key",
        "role_checker",
    }
)
API_PREFIX = "/api"
MSG_ROUTES_GUARDED = "every API route that is not public has an authentication boundary"
MSG_GUARD_EMPTY_TREE = "the route guard finds no authentication in an empty dependency tree"

PUT = "PUT"
STATUS_FORBIDDEN = 403
STATUS_UNPROCESSABLE = 422
PLM_PATH = "/api/settings/integrations/PLM"
SETTING_PATH = "/api/settings/{}"
BLOOM_URL = "https://bloom.example.com"
BLOOM_OTHER_ORIGIN = "https://new.example.com"
BLOOM_SAME_ORIGIN = "https://bloom.example.com/root"
BLOOM_INVALID_PORT = "https://bloom.example.com:not-a-port"
BLOOM_TOKEN = "blm_sync_this-is-a-test-service-token"
BLOOM_KEPT_TOKEN = "blm_sync_keep-this-secret"
BLOOM_MASKED_TOKEN = "********"
BLOOM_TOKEN_PREFIX_LENGTH = 20
BLOOM_TOKEN_FIELD = "bloom_token"
BLOOM_TOKEN_SETTING = "bloom_token_encrypted"
BLOOM_PLAINTEXT = "plaintext"
MSG_PLM_SAVED = "an administrator saves the Bloom URL and token"
MSG_PLM_HAS_TOKEN = "the answer says a token is saved"
MSG_PLM_PREFIX = "the answer shows only the token's first 20 characters"
MSG_PLM_NO_TOKEN_FIELD = "the answer carries no token field"
MSG_PLM_STORED = "the token is stored"
MSG_PLM_ENCRYPTED = "the stored token is not the plain token"
MSG_PLM_GET_NO_TOKEN = "reading the integration never shows the token"
MSG_PLM_GET_NO_FIELD = "reading the integration carries no token field"
MSG_PLM_ORIGIN_REFUSED = "a new Bloom origin with the masked token is refused"
MSG_PLM_ORIGIN_KEPT = "the refused origin change keeps the saved token"
MSG_PLM_SAME_ORIGIN = "a new URL on the same origin with the masked token is saved"
MSG_PLM_SAME_ORIGIN_KEPT = "a same-origin URL change keeps the saved token"
MSG_PLM_INVALID_PORT = "a Bloom URL with an invalid port is refused"
MSG_SETTING_SECRET_READ = "the generic settings endpoint does not read the Bloom secret"
MSG_SETTING_SECRET_WRITE = "the generic settings endpoint does not write the Bloom secret"

NGINX_CONF = "docker/nginx.conf"
SECURITY_HEADERS_CONF = "docker/security-headers.conf"
SECURITY_HEADERS = (
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
    "Content-Security-Policy",
)
NGINX_ADD_HEADER = "add_header"
NGINX_HEADER_LINE = "add_header {} "
NGINX_ALWAYS = "always;"
NGINX_LOCATION = r"^\s*(location[^\n{]*)\{"
NGINX_INCLUDE = "include /etc/nginx/security-headers.conf;"
CSP_HEADER = "Content-Security-Policy"
CSP_SCRIPT_SELF = "script-src 'self'"
CSP_SCRIPT_SOURCE = "script-src"
CSP_UNSAFE_INLINE = "unsafe-inline"
CSP_FRAME_ANCESTORS = "frame-ancestors 'self'"
DOCKERFILE_HEADERS_COPY = "docker/security-headers.conf /etc/nginx/security-headers.conf"
MSG_NGINX_HEADER = "the shared header file sets the security header"
MSG_NGINX_ALWAYS = "every shared header is sent on error responses too"
MSG_NGINX_SERVER_INCLUDE = "the server block includes the shared header file"
MSG_NGINX_LOCATION_INCLUDE = "every location that sets a header of its own includes the shared file"
MSG_CSP_SCRIPT_SELF = "the CSP allows scripts from the app's own origin"
MSG_CSP_NO_INLINE = "the CSP forbids inline script"
MSG_CSP_FRAMES = "the CSP lets only the app's own origin frame it"
MSG_IMAGE_SHIPS_HEADERS = "the image ships the shared header file"

PATCH = "PATCH"
TEST_RUNS_PATH = "/api/test-runs"
TEST_RUN_PATH = "/api/test-runs/{}"
RESULTS_PATH = "/api/results"
RUN_WRITE_OPERATIONS = ("create", "patch", "results-create", "results-update")
PRODUCER_RUN_NAME = "Station run"
PRODUCER_CASE_LIST = "suite"
PRODUCER_HUMAN_RUN = {
    "test_suite_name": "Human-created run",
    "test_case_list": "suite",
    "runner_account": "station-01",
    "status": "Running",
}
PRODUCER_HUMAN_PATCH = {"status": "Cancelled", "total_tests": 99}
PRODUCER_HUMAN_RESULTS = {
    "test_suite_name": "Human results",
    "results": [{"test_class": "Suite", "test_method": "test_one", "passed": True}],
}
PRODUCER_STATION_RUN = {
    "test_suite_name": "Station run",
    "test_case_list": "suite",
    "runner_account": "station-01",
    "status": "Running",
    "url_test_software": "https://example.com/tests.git",
    "ref_test_software": "release",
}
PRODUCER_STATION_COUNTS = {"total_tests": 7, "passed_tests": 5, "failed_tests": 2}
PRODUCER_COUNTS = (7, 5, 2)
PRODUCER_REF = "release"
PRODUCER_UNTOUCHED_TOTAL = 0
PRODUCER_RUN_COUNT = 1
PRODUCER_EVENT_COUNT = 0
MSG_PRODUCER_HUMAN_REFUSED = "a person cannot write a test run record"
MSG_PRODUCER_STATUS_KEPT = "the run keeps its status"
MSG_PRODUCER_TOTAL_KEPT = "the run keeps its test count"
MSG_PRODUCER_NOT_COMPLETED = "the run is not completed"
MSG_PRODUCER_NO_NEW_RUN = "no run is added"
MSG_PRODUCER_NO_EVENT = "no run event is recorded"
MSG_PRODUCER_STATION_CREATES = "a station creates its run"
MSG_PRODUCER_STATION_UPDATES = "a station updates its run"
MSG_PRODUCER_RUN_OWNER = "the run belongs to the station"
MSG_PRODUCER_RUN_COUNTS = "the run keeps the station's counts"
MSG_PRODUCER_RUN_REF = "the run keeps the test software reference"

SETUP_PATH = "/api/setup"
SETUP_STATUS_PATH = "/api/setup/status"
SETUP_PASSWORD = "a-sufficiently-long-passphrase"
SETUP_OWNER = {
    "email": "owner@example.com",
    "password": "a-sufficiently-long-passphrase",
    "full_name": "Instance Owner",
}
SETUP_SECOND_EMAIL = "squatter@example.com"
SETUP_SHORT_PASSWORD = "short"
SETUP_REQUIRED = {"setup_required": True}
SETUP_DONE = {"setup_required": False}
SETUP_ADMIN_ROLE = "admin"
SETUP_USERS = 1
SETUP_RUNNER_KEY = "runner_api_key"
SETUP_LOGIN_SUFFIX = "/login"
STATUS_CONFLICT = 409
MSG_SETUP_STATUS_ANSWERS = "the setup status answers"
MSG_SETUP_REQUIRED = "an instance without users needs setup"
MSG_SETUP_DONE_SEEDED = "an instance with a seeded administrator needs no setup"
MSG_SETUP_CREATED = "setup creates the first administrator"
MSG_SETUP_ADMIN_ROLE = "the first user is an administrator"
MSG_SETUP_ADMIN_ACTIVE = "the first administrator is active"
MSG_SETUP_PASSWORD_HASHED = "the first administrator's password is stored hashed"
MSG_SETUP_DONE = "after setup the instance needs no setup"
MSG_SETUP_SECOND_REFUSED = "a second setup is refused"
MSG_SETUP_ONE_USER = "the refused second setup adds no user"
MSG_SETUP_SHORT_PASSWORD = "setup refuses a password below the shared policy"
MSG_SETUP_NO_SECRET = "setup hands over no runner key"
MSG_SETUP_MESSAGE = "setup answers with a message"
MSG_SETUP_WITHOUT_MAIL = "setup succeeds when mail is unavailable"
MSG_SETUP_MAIL_TO = "the welcome email goes to the new administrator"
MSG_SETUP_MAIL_NAME = "the welcome email names the new administrator"
MSG_SETUP_MAIL_LINK = "the welcome email links to the sign-in page"

CHANNELS_PATH = "/api/settings/notifications/channels"
CHANNEL_PATH = "/api/settings/notifications/channels/{}"
CHANNEL_TEST_PATH = "/api/settings/notifications/channels/{}/test"
CHANNEL_HOOK = "https://hooks.example.com/services/T000/B000/abcdefghijklmnopqrstuvwxyz"
CHANNEL_SECRET = "s3cr3t"
CHANNEL = {
    "name": "qa",
    "format": "slack",
    "url": "https://hooks.example.com/services/T000/B000/abcdefghijklmnopqrstuvwxyz",
    "secret": "s3cr3t",
    "run_filter": "failures",
}
CHANNEL_PREFIX_LENGTH = 40
CHANNEL_PREFIX_ELLIPSIS = "..."
CHANNEL_URL_FIELD = "url"
CHANNEL_SECRET_FIELD = "secret"
CHANNEL_PATCH = {"run_filter": "all", "secret": ""}
CHANNEL_PATCHED_FILTER = "all"
CHANNEL_INVALID = {
    "ftp URL": {"url": "ftp://hooks.example.com/x"},
    "URL with credentials": {"url": "https://user:pw@hooks.example.com/x"},
    "email format": {"format": "email"},
    "unknown run filter": {"run_filter": "sometimes"},
}
CHANNEL_MISSING_ID = 999
CHANNEL_TEST_RESULT = {"delivered": True, "attempts": 1, "status_code": 200, "error": None}
CHANNEL_POST_TEXT = "ok"
STATUS_UNAUTHORIZED = 401
MSG_CHANNEL_CREATED = "an administrator adds a channel"
MSG_CHANNEL_PREFIX = "the answer shows only the URL's first 40 characters"
MSG_CHANNEL_HAS_SECRET = "the answer says a secret is saved"
MSG_CHANNEL_NO_URL = "the answer carries no URL field"
MSG_CHANNEL_NO_SECRET = "the answer carries no secret field"
MSG_CHANNEL_HOOK_HIDDEN = "the answer never shows the URL"
MSG_CHANNEL_LISTED = "the channels are listed"
MSG_CHANNEL_LIST_HOOK = "the list never shows the URL"
MSG_CHANNEL_LIST_SECRET = "the list never shows the secret"
MSG_CHANNEL_URL_ENCRYPTED = "the stored URL is not the plain URL"
MSG_CHANNEL_SECRET_ENCRYPTED = "the stored secret is not the plain secret"
MSG_CHANNEL_PATCHED = "an administrator changes a channel"
MSG_CHANNEL_FILTER = "the run filter is changed"
MSG_CHANNEL_SECRET_CLEARED = "an empty secret clears the saved secret"
MSG_CHANNEL_URL_KEPT = "a change without a URL keeps the saved URL"
MSG_CHANNEL_INVALID = "a channel with invalid input is refused"
MSG_CHANNEL_VALID = "a valid channel is added"
MSG_CHANNEL_DUPLICATE = "a second channel with the same name is refused"
MSG_CHANNEL_DELETED = "an administrator deletes a channel"
MSG_CHANNEL_DELETED_AGAIN = "a deleted channel is not found"
MSG_CHANNEL_MISSING = "changing a channel that does not exist is not found"
MSG_CHANNEL_TEST_SENT = "a test message is sent"
MSG_CHANNEL_TEST_RESULT = "the test message is delivered at the first attempt"
MSG_CHANNEL_TEST_URL = "the test message goes to the channel's URL"
MSG_CHANNEL_SIGNED_OUT = "a signed-out visitor cannot list the channels"

PRODUCTS_PATH = "/api/products"
PRODUCT_PATH = "/api/products/{}"
PRODUCT = {"name": "Gateway ECU", "description": "Main gateway"}
PRODUCT_DUPLICATE = {"name": "Duplicate", "description": None}
PRODUCT_DUPLICATE_TEXT = "already exists"
PRODUCT_NAMES = ("Zebra", "Alpha", "Mango")
PRODUCT_FETCHED = "Fetchable"
PRODUCT_DELETED = "Deletable"
PRODUCT_MISSING_ID = 99999
PRODUCT_SIGNED_OUT_CALLS = (
    ("GET", "/api/products"),
    ("POST", "/api/products"),
    ("GET", "/api/products/1"),
    ("DELETE", "/api/products/1"),
)
PRODUCT_SIGNED_OUT_BODY = {"name": "x"}
STATIONS_STATUS_PATH = "/api/runners/status"
STATION_PATH = "/api/runners/{}"
STATION_PASSWORD = "hashed"
STATION_TOKEN_PREFIX = "token-"
STATION_LISTED = "station-01"
STATION_SOLO = "station-solo"
STATION_GONE = "station-gone"
STATION_GHOST = "ghost"
STATION_SIGNED_OUT_CALLS = (
    ("GET", "/api/runners/status"),
    ("GET", "/api/runners/station-01"),
    ("DELETE", "/api/runners/station-01"),
)
MSG_PRODUCT_CREATED = "an administrator adds a product"
MSG_PRODUCT_NAME = "the product keeps its name"
MSG_PRODUCT_FIRST = "the first product of a name is added"
MSG_PRODUCT_DUPLICATE = "a second product of the same name is refused"
MSG_PRODUCT_DUPLICATE_TEXT = "the refusal says the product already exists"
MSG_PRODUCT_SORTED = "the products are listed by name"
MSG_PRODUCT_FETCHED = "one product is read"
MSG_PRODUCT_MISSING = "an unknown product is not found"
MSG_PRODUCT_DELETED = "an administrator deletes a product"
MSG_PRODUCT_GONE = "the deleted product is gone"
MSG_PRODUCT_DELETE_MISSING = "deleting an unknown product is not found"
MSG_PRODUCT_SIGNED_OUT = "a signed-out visitor cannot reach the products"
MSG_STATION_STATUS = "the Test Station status answers"
MSG_STATION_LISTED = "the status lists the registered Test Station"
MSG_STATION_FETCHED = "one Test Station is read"
MSG_STATION_ACCOUNT = "the Test Station keeps its account"
MSG_STATION_MISSING = "an unknown Test Station is not found"
MSG_STATION_DELETED = "an administrator deletes a Test Station"
MSG_STATION_GONE = "the deleted Test Station is gone"
MSG_STATION_DELETE_MISSING = "deleting an unknown Test Station is not found"
MSG_STATION_SIGNED_OUT = "a signed-out visitor cannot reach the Test Stations"

UPLOADER = {
    "id": 7,
    "email": "uploader@example.com",
    "full_name": "Uploader",
    "hashed_password": "hash",
}
UPLOAD_MAX_SIZE = 25
UPLOAD_MAX_RUN_BYTES = 250
UPLOAD_EXISTING = {
    "filename": "existing",
    "original_filename": "existing",
    "content_type": "text/plain",
    "size_bytes": 226,
    "storage_path": "existing",
    "test_run_id": 1,
}
UPLOAD_RUN_ID = 1
UPLOAD_REMAINING = 24
UPLOADS_PER_WINDOW = 2
STATUS_TOO_MANY = 429
UPLOAD_RATE_TEXT = "rate"
CLEANUP_RETENTION_DAYS = 30
CLEANUP_EXPIRED_AGE = timedelta(days=31)
CLEANUP_ORPHAN_AGE = timedelta(hours=2)
CLEANUP_ORPHAN = "orphan.log"
CLEANUP_ORPHAN_BYTES = b"orphan"
CLEANUP_EXPIRED = "expired.log"
CLEANUP_EXPIRED_BYTES = b"expired"
CLEANUP_LEASE = "expired-lease"
CLEANUP_PRINCIPAL = "user:99"
CLEANUP_LEASE_BYTES = 25
CLEANUP_LEASE_AGE = timedelta(minutes=1)
CLEANUP_ATTEMPT_AGE = timedelta(minutes=16)
CLEANUP_GRACE_SECONDS = 3600
CLEANUP_REMOVED = 1
MSG_UPLOAD_REMAINING = "a run's upload reserves only its remaining capacity"
MSG_UPLOAD_ONE_ACTIVE = "a second active upload of the same person is refused"
MSG_UPLOAD_TOO_MANY = "the refusal is too many requests"
MSG_UPLOAD_RATE = "a third upload start in the window is refused"
MSG_UPLOAD_RATE_TEXT = "the refusal names the rate limit"
MSG_CLEANUP_EXPIRED = "the cleanup removes the one expired artifact"
MSG_CLEANUP_ORPHANS = "the cleanup removes the one old orphan file"
MSG_CLEANUP_EXPIRED_FILE = "the expired artifact's file is removed"
MSG_CLEANUP_ORPHAN_FILE = "the orphan file is removed"
MSG_CLEANUP_LEASE = "the expired upload lease is removed"

RESULTS_RUN_PATH = "/api/results/{}"
RESULT_DETAIL_PATH = "/api/results/detail/{}"
RESULT_TRACE = 'Traceback (most recent call last):\n  File "t.py", line 9\nAssertionError: 3 != 4'
RESULT_ASSERTION_TRACE = "assertion-level trace"
RESULT_FAILURE = {
    "test_class": "SmokeTests",
    "test_method": "test_boot",
    "passed": False,
    "duration_seconds": 1.5,
    "error_message": "3 != 4",
    "traceback": 'Traceback (most recent call last):\n  File "t.py", line 9\nAssertionError: 3 != 4',
    "assertions": [{"passed": False, "message": "3 != 4", "traceback": "assertion-level trace"}],
    "metadata": {"test_case_class": "SmokeTests", "tc_id": "PRJ-TC-001"},
}
RESULT_RUN = {"test_suite_name": "Nightly", "test_case_list": "SmokeTests"}
RESULT_ORDERED_RUN = {"test_suite_name": "Ordered", "test_case_list": "SmokeTests"}
RESULT_ORDER = ["test_a", "test_b"]
RESULT_ROWS = 1
RESULT_TRACE_FIELD = "traceback"
RESULT_LIST_FIELDS = (
    "id",
    "test_class",
    "test_method",
    "passed",
    "duration_seconds",
    "error_message",
    "assertions",
    "test_metadata",
    "work_package_id",
    "created_at",
    "test_run_id",
)
RESULT_MISSING_RUN = 999999
MSG_RESULT_UPLOADED = "a station uploads a failed result to its run"
MSG_RESULT_ONE_ROW = "the listing has the one result"
MSG_RESULT_NO_TRACE = "the listing leaves out the method traceback"
MSG_RESULT_FIELD = "the listing keeps the column the run detail draws"
MSG_RESULT_ASSERTION_TRACE = "the listing keeps the trace inside an assertion"
MSG_RESULT_ORDER = "the listing orders results as they were recorded"
MSG_RESULT_MISSING_RUN = "the results of an unknown run are not found"
MSG_RESULT_DETAIL_TRACE = "a single result still carries the method traceback"
MSG_RESULT_STORED_TRACE = "the method traceback is still stored on upload"

RELEASE_SCRIPT = "scripts/image_release.py"
RELEASE_MODULE = "image_release"
RELEASE_DIGEST = "sha256:" + "a" * 64
RELEASE_OTHER_DIGEST = "sha256:" + "b" * 64
RELEASE_REPOSITORY = "registry.example.com/team/product"
RELEASE_IMAGE = RELEASE_REPOSITORY + "@" + RELEASE_DIGEST
RELEASE_MALFORMED = [
    "",
    "-v",
    "--format={{json .}}",
    "image:stable",
    "team/product:1.1.0",
    "registry.example.com/Team/product:1.1.0",
    "registry.example.com/team/product@sha256:abc",
    "registry.example.com/team/product:sha-1@" + RELEASE_DIGEST,
    "registry.example.com/team/product:1.1.0 --push",
    "registry.example.com/team/product:-latest",
    "registry.example.com/team/product/",
    None,
]
RELEASE_WELL_FORMED = [
    RELEASE_REPOSITORY,
    RELEASE_REPOSITORY + ":sha-" + "0" * 40,
    RELEASE_REPOSITORY + ":v1.2.0",
    RELEASE_IMAGE,
    "localhost:5000/team/product_name:1.2.0-beta.1",
    "registry.example.com:443/a/b-c/d__e:latest",
]
RELEASE_OLDER_ALIASES = ["image:v1.0.0", "image:1.0.0", "image:1", "image:1.0", "image:stable"]
RELEASE_OLDER_KEPT = ["image:v1.0.0", "image:1.0.0"]
RELEASE_STABLE = ["image:stable"]
RELEASE_LATEST = ["image:latest"]
RELEASE_OLDER_REF = "refs/tags/v1.0.0"
RELEASE_CURRENT_REF = "refs/tags/v1.1.0"
RELEASE_BRANCH_REF = "refs/heads/main"
RELEASE_PRERELEASE_REF = "refs/tags/v1.2.0-beta.1"
RELEASE_LATEST_TAG = "v1.1.0"
RELEASE_VERSION_ALIASES = [RELEASE_REPOSITORY + ":stable", RELEASE_REPOSITORY + ":1.1.0"]
RELEASE_REPEATED_ALIASES = [RELEASE_REPOSITORY + ":1.1.0", RELEASE_REPOSITORY + ":stable"]
RELEASE_STABLE_ALIASES = [RELEASE_REPOSITORY + ":stable"]
RELEASE_MALFORMED_PROMOTIONS = {
    "a dash alias": (RELEASE_IMAGE, [RELEASE_REPOSITORY + ":stable", "-x"]),
    "an alias without registry": (RELEASE_IMAGE, ["image:stable"]),
    "a dash image": ("-" + RELEASE_REPOSITORY + "@" + RELEASE_DIGEST, [RELEASE_REPOSITORY + ":stable"]),
}
RELEASE_DOCKER_INSPECT = ["docker", "buildx", "imagetools", "inspect"]
RELEASE_PROMOTIONS = 2
RUNTIME_ERROR = "RuntimeError"
RELEASE_OVERWRITE_TEXT = "Refusing to overwrite"
RELEASE_VERIFY_TEXT = "Digest verification"
RELEASE_INVALID_TEXT = "Invalid image reference"
MSG_RELEASE_OLDER = "an older release does not move the floating tags"
MSG_RELEASE_CURRENT = "the current release promotes stable"
MSG_RELEASE_STALE_BRANCH = "a stale branch run does not promote latest"
MSG_RELEASE_PRERELEASE = "a prerelease does not promote stable"
MSG_RELEASE_CONFLICT = "a version conflict stops the promotion"
MSG_RELEASE_CONFLICT_TEXT = "the conflict refuses to overwrite the published version"
MSG_RELEASE_NOTHING_CHANGED = "no alias is changed before the conflict is found"
MSG_RELEASE_REPEATED = "a repeated promotion points every alias again"
MSG_RELEASE_SAME_IMAGE = "every alias points at the same image digest"
MSG_RELEASE_MISMATCH = "a digest mismatch after promotion fails"
MSG_RELEASE_MISMATCH_TEXT = "the failure names the digest verification"
MSG_RELEASE_REFUSED = "a malformed reference is refused"
MSG_RELEASE_REFUSED_TEXT = "the refusal names the invalid image reference"
MSG_RELEASE_NO_DOCKER = "docker is not called for a malformed reference"
MSG_RELEASE_DIGEST = "a registry reference's digest is read"
MSG_RELEASE_INSPECTED = "docker inspects exactly that reference"
MSG_RELEASE_CHECK = "the reference check accepts exactly what digest passes to docker"
MSG_RELEASE_NOT_INSPECTED = "the registry is not asked about a malformed promotion"
MSG_RELEASE_NOT_EXECUTED = "no alias is changed for a malformed promotion"

API_KEYS_PATH = "/api/runners/api-keys"
REGISTER_PATH = "/api/runners/register"
API_KEY_HEADER = "X-API-Key"
STATION_REGISTRATION = {
    "username": "whatever-the-station-typed",
    "password": "a-very-long-runner-password-123",
    "socket_port": 53035,
}
STATION_NAMED = "station-01"
STATION_OTHER = "station-02"
STATION_RENAMED = "station-01-renamed"
STATION_MOVED = "moved"
STATION_IGNORED_USERNAME = "ignored-anyway"
STATION_UNKNOWN = "nobody"
STATION_UNKNOWN_NEW = "somebody"
STATION_KEY_LABEL = "station-01 key"
STATION_UNNAMED_LABEL = "unnamed key"
STATION_SECOND_LABEL = "second"
STATION_BAD_NAMES = ("Demo's station", "lab 2", "station/a", "station#3", "ab")
STATION_TAKEN_TEXT = "already named"
STATION_RESERVED_TEXT = "already reserves"
MSG_KEY_MINTED = "an administrator mints the enrolment keys"
MSG_STATION_REGISTERED = "the station registers with the key"
MSG_STATION_NAME_WINS = "the name the administrator chose wins"
MSG_STATION_OWN_NAME = "a key without a name leaves the station its own"
MSG_STATION_TOKEN_ID = "the station's token identifies it by id"
MSG_STATION_NAME_TAKEN = "a name a station already has is refused"
MSG_STATION_NAME_TAKEN_TEXT = "the refusal says a station is already named so"
MSG_STATION_NAME_RESERVED = "a name an unused key reserves is refused"
MSG_STATION_NAME_RESERVED_TEXT = "the refusal says an unused key already reserves the name"
MSG_STATION_BAD_NAME = "a name that would break a URL is refused"
MSG_STATION_RENAMED = "an administrator renames a station"
MSG_STATION_NEW_NAME = "the station answers with its new name"
MSG_STATION_KEY_RENAMED = "the station's key carries the new name"
MSG_STATION_TOKEN_KEPT = "a renamed station's token still authenticates"
MSG_STATION_TOKEN_NAME = "the token resolves to the renamed station"
MSG_STATION_RENAME_TAKEN = "renaming onto a taken name is refused"
MSG_STATION_RENAME_UNKNOWN = "renaming an unknown station is not found"

SMOKE_SCRIPT = "scripts/e2e_image_smoke.sh"
SMOKE_IMAGE = "registry.example.com/team/bud:test"
SMOKE_ARGV_LOG = "docker-argv.jsonl"
SMOKE_ARGV_SETTING = "DOCKER_ARGV_LOG"
SMOKE_RECORDING_DOCKER = """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["DOCKER_ARGV_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")
if "current" in args:
    print("0123456789ab (head)")
    sys.exit(0)
if args and args[0] == "run" and "--name" in args:
    name = args[args.index("--name") + 1]
    if name.startswith("bud-e2e-app-"):
        sys.exit(23)
"""
SMOKE_RUN_PREFIX = ["run", "-d", "--name"]
SMOKE_APP_NAME = "bud-e2e-app-"
SMOKE_ADMIN_NAME = "ADMIN_FULL_NAME=E2E Admin"
SMOKE_DOCKER = """#!/usr/bin/env python3
import sys
args = sys.argv[1:]
if args[0] == "port":
    print("127.0.0.1:18080")
elif "current" in args:
    print("017_release120 (head)")
"""
SMOKE_CURL = """#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from urllib.parse import urlparse
args = sys.argv[1:]
url = next(arg for arg in args if arg.startswith("http://"))
path = urlparse(url).path
headers = [args[i + 1] for i, arg in enumerate(args) if arg == "-H"]
fields = [args[i + 1] for i, arg in enumerate(args) if arg == "-F"]
station = "Authorization: Bearer station-fixture-token" in headers
admin = "Authorization: Bearer admin-fixture-token" in headers
if path == "/api/health":
    print('{"status":"healthy"}')
elif path == "/api/ready":
    print('{"status":"ready","database":"connected"}')
elif path == "/api/version":
    root = Path(sys.argv[0]).parent
    print(json.dumps({"version": (root / "version").read_text()}))
elif path == "/api/auth/login":
    print('{"access_token":"admin-fixture-token"}')
elif path == "/api/products":
    assert admin
    print('[]')
elif path == "/api/runners/api-keys":
    assert admin
    print('{"api_key":"enrolment-fixture-key"}')
elif path == "/api/runners/register":
    assert "X-API-Key: enrolment-fixture-key" in headers
    print('{"token":"station-fixture-token"}')
elif path == "/api/test-runs":
    assert station
    print('{"id":7}')
elif path == "/api/uploads":
    if admin:
        if "-w" not in args:
            sys.exit(22)
        print("403", end="")
    else:
        assert station
        assert "run_id=7" in fields
        print('{"id":9}')
elif path == "/api/uploads/info/9":
    assert admin
    print('{"id":9}')
elif path == "/api/uploads/9":
    assert admin
    Path(args[args.index("-o") + 1]).write_bytes(b"A" * 2097152)
else:
    raise AssertionError(path)
"""
SMOKE_VERSION_FILE = "version"
SMOKE_EXIT_OK = 0
SMOKE_VERIFIED = "verified sha256"
SMOKE_PASS = "PASS: Bud published image"
MSG_SMOKE_ADMIN_NAME = "the administrator's full name stays one docker environment argument"
MSG_SMOKE_EXIT = "the smoke script passes with station-owned uploads"
MSG_SMOKE_VERIFIED = "the smoke script verifies the downloaded evidence's SHA-256"
MSG_SMOKE_PASS = "the smoke script reports the published image passed"
