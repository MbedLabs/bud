"""Set-up of the Bud suites: paths, routes and limits of the UI under test."""

from pathlib import Path


class UiCliAuth:
    """Set-up of the ui_cli_auth suite."""

    DIST = Path(__file__).resolve().parents[2] / "ui" / "dist"
    HOST = "127.0.0.1"
    PAGE_ROUTE = "/auth/cli?session_id={session_id}"
    API_PATTERN = "**/api/**"
    REFRESH_PATH = "/api/auth/refresh"
    ME_PATH = "/api/auth/me"
    SESSION_PATH = "/api/auth/cli/sessions/{session_id}"
    JSON = "application/json"
    TIMEOUT_MS = 10000
