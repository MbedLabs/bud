from __future__ import annotations

import pytest
from app.api.auth import get_current_user
from app.main import app
from app.models import TestStation
from app.models.user import User, UserRole


API_KEY_HEADERS = {"X-API-Key": "test-runner-api-key"}


def _register_station(client, account: str) -> str:
    response = client.post(
        "/api/teststations/register",
        headers=API_KEY_HEADERS,
        json={
            "username": account,
            "password": "a-long-teststation-password-123",
            "socket_port": 53035,
            "location": "lab-a",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["token"]


def test_teststation_heartbeat_requires_bearer_token(client):
    _register_station(client, "station-no-auth")

    response = client.post(
        "/api/teststations/heartbeat",
        json={"teststation_account": "station-no-auth"},
    )

    assert response.status_code == 401


def test_teststation_cannot_heartbeat_another_station(client):
    station_a_token = _register_station(client, "station-a")
    _register_station(client, "station-b")

    response = client.post(
        "/api/teststations/heartbeat",
        headers={"Authorization": f"Bearer {station_a_token}"},
        json={"teststation_account": "station-b"},
    )

    assert response.status_code == 403


def test_teststation_can_heartbeat_itself(client):
    token = _register_station(client, "station-self")

    response = client.post(
        "/api/teststations/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json={"teststation_account": "station-self"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["account"] == "station-self"


def test_teststation_reregistration_rotates_token_with_matching_password(client):
    old_token = _register_station(client, "station-rotate")

    response = client.post(
        "/api/teststations/register",
        headers=API_KEY_HEADERS,
        json={
            "username": "station-rotate",
            "password": "a-long-teststation-password-123",
            "socket_port": 53036,
            "location": "lab-b",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["token"] != old_token


@pytest.mark.parametrize("password", ["wrong-password-123", "another-wrong-password"])
def test_teststation_reregistration_rejects_wrong_password(client, password):
    _register_station(client, "station-password")

    response = client.post(
        "/api/teststations/register",
        headers=API_KEY_HEADERS,
        json={
            "username": "station-password",
            "password": password,
            "socket_port": 53035,
        },
    )

    assert response.status_code == 400
    assert "password" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_teststation_status_and_detail_require_user_auth(
    unauthenticated_client, db_session
):
    station = TestStation(
        account="station-private",
        password_hash="x",
        token="stored-token",
        is_active=True,
    )
    db_session.add(station)
    await db_session.commit()

    status_response = unauthenticated_client.get("/api/teststations/status")
    detail_response = unauthenticated_client.get("/api/teststations/station-private")

    assert status_response.status_code == 401
    assert detail_response.status_code == 401


@pytest.mark.asyncio
async def test_shared_registration_key_cannot_delete_teststation(
    unauthenticated_client, db_session
):
    station = TestStation(
        account="station-api-key-delete",
        password_hash="x",
        token="stored-token",
        is_active=True,
    )
    db_session.add(station)
    await db_session.commit()

    response = unauthenticated_client.delete(
        "/api/teststations/station-api-key-delete",
        headers=API_KEY_HEADERS,
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_viewer_cannot_delete_teststation(client, db_session):
    station = TestStation(
        account="station-viewer-delete",
        password_hash="x",
        token="stored-token",
        is_active=True,
    )
    viewer = User(
        id=22,
        email="viewer-delete@example.com",
        full_name="Viewer",
        hashed_password="x",
        role=UserRole.viewer,
        is_active=True,
    )
    db_session.add_all([station, viewer])
    await db_session.commit()

    async def override_viewer():
        return viewer

    app.dependency_overrides[get_current_user] = override_viewer
    try:
        response = client.delete("/api/teststations/station-viewer-delete")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_delete_teststation(client, db_session):
    station = TestStation(
        account="station-admin-delete",
        password_hash="x",
        token="stored-token",
        is_active=True,
    )
    db_session.add(station)
    await db_session.commit()

    response = client.delete("/api/teststations/station-admin-delete")

    assert response.status_code == 204, response.text
