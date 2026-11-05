"""Values the Bud suites use: fixtures, positions and statuses."""


class UiCliAuth:
    """Values of the ui_cli_auth suite."""

    SESSION_ID = "0f8e6c1a-2b3d-4e5f-8a9b-0c1d2e3f4a5b"
    BOXES = 8
    BOX_ORDER = ["box"] * 4 + ["-"] + ["box"] * 4
    USER = {
        "id": 7,
        "email": "viewer@example.com",
        "full_name": "Viewer",
        "role": "viewer",
        "is_active": True,
        "created_at": "2026-11-05T10:00:00Z",
        "updated_at": "2026-11-05T10:00:00Z",
        "permissions": [],
    }
    SIGN_IN = {"access_token": "fixture-token", "token_type": "bearer", "user": USER}
    SESSION = {
        "session_id": SESSION_ID,
        "client_name": "Terminal",
        "mode": "callback",
        "redirect_uri": "http://127.0.0.1:41234/callback",
        "expires_at": "2099-01-01T00:00:00Z",
        "created_at": "2026-11-05T10:00:00Z",
        "consumed": False,
    }
    NOT_FOUND = {"detail": "Not Found"}
    OK = 200
    MISSING = 404
