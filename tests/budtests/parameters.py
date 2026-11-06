"""Values the Bud suites use: fixtures, inputs, positions and statuses."""


class UiCliAuth:
    """Values of the ui_cli_auth suite."""

    SESSION_ID = "0f8e6c1a-2b3d-4e5f-8a9b-0c1d2e3f4a5b"
    BOXES = 8
    BOX_ORDER = ["box"] * 4 + ["-"] + ["box"] * 4
    TYPED = "buuzwhvv"
    PASTED = "buuz whvv"
    CODE = "BUUZ-WHVV"
    CHARACTERS = list("BUUZWHVV")
    EMPTY = [""] * 8
    SEVEN = "buuzwhv"
    EIGHTH = "v"
    WRONG = "aaaaaaaa"
    EXCHANGE_CODE = "single-use-exchange-code"
    CREATED_AT = "2099-01-01T00:00:00Z"
    EXPIRES_AT = "2099-01-01T00:10:00Z"
    CLIENT_NAME = "Terminal client"
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
    CODE_SESSION = {
        "session_id": SESSION_ID,
        "client_name": CLIENT_NAME,
        "mode": "code",
        "redirect_uri": None,
        "created_at": CREATED_AT,
        "expires_at": EXPIRES_AT,
        "consumed": False,
    }
    CALLBACK = "http://127.0.0.1:{port}/callback"
    APPROVED = "http://127.0.0.1:{port}/callback?code=once&state=original"
    SHOWN_APPROVED = {
        "4567": "http://127.0.0.1:4567/callback?code=once&state=original",
        "80": "http://127.0.0.1/callback?code=once&state=original",
    }
    CALLBACK_PORT = "4567"
    OUTSIDE = "https://evil.test/callback?code=once&state=original"
    EXCHANGE = {"exchange_code": EXCHANGE_CODE, "expires_at": "2099-01-01T00:00:00"}
    SERVER_TEXT = "Invalid or expired authorization session"
    REFUSED = {"detail": SERVER_TEXT}
    LIMITED = {"detail": "Rate limit exceeded"}
    NOT_FOUND = {"detail": "Not Found"}
    NOTHING = {}
    OK = 200
    BAD_REQUEST = 400
    MISSING = 404
    TOO_MANY = 429
    SERVER_ERROR = 500
    ONE = 1
    TWO = 2
    HOLD = "hold"
