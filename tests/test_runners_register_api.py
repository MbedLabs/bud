"""
Tests for ``POST /api/runners/register`` — guarded by the X-API-Key
shared secret (see ``app.core.deps.require_runner_api_key``).

These tests pin the contract the ``bud_runner`` CLI relies on:
  * Missing X-API-Key  → 422 (FastAPI header validation).
  * Wrong X-API-Key    → 403.
  * Correct X-API-Key  → 201 and a runner token is returned.
"""

from __future__ import annotations


from app.api.auth import get_current_user
from app.main import app
from app.models.user import User, UserRole

API_KEY_HEADERS = {"X-API-Key": "test-runner-api-key"}

VALID_PAYLOAD = {
    "username": "runner-test-01",
    "password": "a-very-long-runner-password-123",
    "socket_port": 53035,
}


def test_register_without_api_key_is_rejected(client):
    response = client.post("/api/runners/register", json=VALID_PAYLOAD)
    # Header(..., alias="X-API-Key") → missing required header → 422
    assert response.status_code == 422, response.text


def test_register_with_wrong_api_key_is_forbidden(client):
    response = client.post(
        "/api/runners/register",
        json=VALID_PAYLOAD,
        headers={"X-API-Key": "not-the-secret"},
    )
    assert response.status_code == 403, response.text


def test_register_with_correct_api_key_creates_runner(client):
    response = client.post(
        "/api/runners/register",
        json=VALID_PAYLOAD,
        headers={"X-API-Key": "test-runner-api-key"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["account"] == VALID_PAYLOAD["username"]
    assert body["token"]  # non-empty JWT


def test_register_same_username_reauthenticates(client):
    headers = {"X-API-Key": "test-runner-api-key"}

    first = client.post("/api/runners/register", json=VALID_PAYLOAD, headers=headers)
    assert first.status_code == 201

    second = client.post("/api/runners/register", json=VALID_PAYLOAD, headers=headers)
    assert second.status_code == 201
    assert "token" in second.json()


def test_register_existing_username_wrong_password_fails(client):
    headers = {"X-API-Key": "test-runner-api-key"}

    first = client.post("/api/runners/register", json=VALID_PAYLOAD, headers=headers)
    assert first.status_code == 201

    bad_payload = dict(VALID_PAYLOAD)
    bad_payload["password"] = "wrong-password"
    second = client.post("/api/runners/register", json=bad_payload, headers=headers)
    assert second.status_code == 400
    assert "does not match" in second.json()["detail"].lower()


def test_shared_registration_key_cannot_delete_runner(unauthenticated_client):
    registered = unauthenticated_client.post(
        "/api/runners/register",
        json=VALID_PAYLOAD,
        headers=API_KEY_HEADERS,
    )
    assert registered.status_code == 201, registered.text

    response = unauthenticated_client.delete(
        f"/api/runners/{VALID_PAYLOAD['username']}",
        headers=API_KEY_HEADERS,
    )

    assert response.status_code == 401


def test_viewer_cannot_delete_runner(client):
    registered = client.post(
        "/api/runners/register",
        json=VALID_PAYLOAD,
        headers=API_KEY_HEADERS,
    )
    assert registered.status_code == 201, registered.text
    viewer = User(
        id=55,
        email="runner-viewer@example.com",
        full_name="Viewer",
        hashed_password="x",
        role=UserRole.viewer,
        is_active=True,
    )

    async def override_viewer():
        return viewer

    app.dependency_overrides[get_current_user] = override_viewer
    try:
        response = client.delete(f"/api/runners/{VALID_PAYLOAD['username']}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403


def test_admin_can_delete_runner(client):
    registered = client.post(
        "/api/runners/register",
        json=VALID_PAYLOAD,
        headers=API_KEY_HEADERS,
    )
    assert registered.status_code == 201, registered.text

    response = client.delete(f"/api/runners/{VALID_PAYLOAD['username']}")

    assert response.status_code == 204, response.text
