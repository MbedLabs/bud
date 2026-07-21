"""Refresh-token flow against real PostgreSQL.

Exercises the httpOnly cookie, single-use rotation, and server-side revocation
end to end (real login, real DB-backed user_tokens rows, no overrides).
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    "postgres" not in os.environ.get("DATABASE_URL", ""),
    reason="requires a PostgreSQL DATABASE_URL (CI-only)",
)

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "ci-admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ci-admin-password-123")
COOKIE = "bud_refresh_token"


def _login(client):
    client.cookies.clear()
    resp = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp


def test_login_sets_httponly_refresh_cookie(client):
    resp = _login(client)
    set_cookie = resp.headers.get("set-cookie", "")
    assert COOKIE in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/auth" in set_cookie
    assert client.cookies.get(COOKIE)  # jar now holds the refresh cookie


def test_refresh_issues_a_working_access_token(client):
    _login(client)
    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 200, resp.text
    new_access = resp.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200
    assert me.json()["email"] == ADMIN_EMAIL


def test_refresh_without_cookie_is_rejected(client):
    client.cookies.clear()
    assert client.post("/api/auth/refresh").status_code == 401


def test_refresh_rotates_and_replayed_old_token_is_rejected(client):
    _login(client)
    old_value = client.cookies.get(COOKIE)

    first = client.post("/api/auth/refresh")  # rotates: jar now holds a new token
    assert first.status_code == 200
    new_value = client.cookies.get(COOKIE)
    assert new_value and new_value != old_value

    # Replaying the burned original refresh token must fail.
    client.cookies.clear()
    replay = client.post("/api/auth/refresh", cookies={COOKIE: old_value})
    assert replay.status_code == 401


def test_logout_revokes_refresh_token(client):
    _login(client)
    assert client.post("/api/auth/logout").status_code == 200
    # The refresh token no longer works after logout.
    assert client.post("/api/auth/refresh").status_code == 401
