"""Tests for ``POST /api/runners/register`` — guarded by a Test Station enrolment
key (see ``app.core.deps.require_runner_api_key``).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.api.auth import get_current_user
from app.core.runner_keys import mint_key
from app.core.security import get_password_hash
from app.main import app
from app.models import Runner, RunnerApiKey
from app.models.user import User, UserRole

VALID_PAYLOAD = {
    "username": "runner-test-01",
    "password": "a-very-long-runner-password-123",
    "socket_port": 53035,
}


@pytest.fixture(autouse=True)
def _no_rate_limit():
    """The limiter guards registration at 10/minute; these tests are not about it."""
    from app.core.deps import limiter

    limiter.enabled = False
    yield
    limiter.enabled = True


def _mint(client, label: str = "bench-a") -> str:
    """Mint a key through the admin endpoint and return the plaintext."""
    response = client.post("/api/runners/api-keys", json={"label": label})
    assert response.status_code == 201, response.text
    return response.json()["api_key"]


async def _seed_key(db_session, label: str = "seeded") -> str:
    """Mint a key straight into the database, for unauthenticated callers."""
    record, plaintext = mint_key(label=label, created_by_user_id=None)
    db_session.add(record)
    await db_session.commit()
    return plaintext


def test_register_without_api_key_is_rejected(client):
    response = client.post("/api/runners/register", json=VALID_PAYLOAD)
    # Header(..., alias="X-API-Key") → missing required header → 422
    assert response.status_code == 422, response.text


def test_register_with_unknown_api_key_is_forbidden(client):
    response = client.post(
        "/api/runners/register",
        json=VALID_PAYLOAD,
        headers={"X-API-Key": "budrnr_not-a-key-anyone-ever-issued"},
    )
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_register_with_a_minted_key_creates_and_pins(client, db_session):
    key = _mint(client)

    response = client.post(
        "/api/runners/register",
        json=VALID_PAYLOAD,
        headers={"X-API-Key": key},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["account"] == VALID_PAYLOAD["username"]
    assert body["token"]  # non-empty JWT

    # The key now names this station, and only this station.
    runner = (
        await db_session.execute(select(Runner).where(Runner.account == VALID_PAYLOAD["username"]))
    ).scalar_one()
    record = (await db_session.execute(select(RunnerApiKey))).scalar_one()
    assert record.runner_id == runner.id
    assert record.last_used_at is not None


def test_register_same_username_reauthenticates(client):
    key = _mint(client)
    headers = {"X-API-Key": key}

    first = client.post("/api/runners/register", json=VALID_PAYLOAD, headers=headers)
    assert first.status_code == 201

    second = client.post("/api/runners/register", json=VALID_PAYLOAD, headers=headers)
    assert second.status_code == 201
    assert "token" in second.json()


def test_register_existing_username_wrong_password_fails(client):
    headers = {"X-API-Key": _mint(client)}

    first = client.post("/api/runners/register", json=VALID_PAYLOAD, headers=headers)
    assert first.status_code == 201

    bad_payload = dict(VALID_PAYLOAD)
    bad_payload["password"] = "wrong-password"
    second = client.post("/api/runners/register", json=bad_payload, headers=headers)
    assert second.status_code == 400
    assert "does not match" in second.json()["detail"].lower()


def test_a_pinned_key_cannot_enrol_a_different_station(client):
    """The impersonation, at enrolment rather than at upload."""
    headers = {"X-API-Key": _mint(client)}

    first = client.post("/api/runners/register", json=VALID_PAYLOAD, headers=headers)
    assert first.status_code == 201

    other = dict(VALID_PAYLOAD)
    other["username"] = "runner-test-02"
    second = client.post("/api/runners/register", json=other, headers=headers)

    assert second.status_code == 403, second.text
    assert "another Test Station" in second.json()["detail"]


def test_a_second_key_cannot_displace_the_first(client):
    """A leaked key plus a known password must not silently take a station over."""
    first_key = {"X-API-Key": _mint(client, "original")}
    first = client.post("/api/runners/register", json=VALID_PAYLOAD, headers=first_key)
    assert first.status_code == 201

    second_key = {"X-API-Key": _mint(client, "interloper")}
    response = client.post("/api/runners/register", json=VALID_PAYLOAD, headers=second_key)

    assert response.status_code == 409, response.text
    assert "already has an API key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_a_key_adopts_a_station_that_has_none(client, db_session):
    """The upgrade path: stations enrolled before keys existed re-register onto one."""
    legacy = Runner(
        account="legacy-bench",
        password_hash=get_password_hash(VALID_PAYLOAD["password"]),
        token="legacy-token",
        socket_port=53035,
    )
    db_session.add(legacy)
    await db_session.commit()
    await db_session.refresh(legacy)

    payload = dict(VALID_PAYLOAD)
    payload["username"] = "legacy-bench"
    response = client.post(
        "/api/runners/register",
        json=payload,
        headers={"X-API-Key": _mint(client, "for-legacy")},
    )

    assert response.status_code == 201, response.text
    record = (await db_session.execute(select(RunnerApiKey))).scalar_one()
    assert record.runner_id == legacy.id


@pytest.mark.asyncio
async def test_enrolment_key_cannot_delete_a_station(unauthenticated_client, db_session):
    key = await _seed_key(db_session)
    headers = {"X-API-Key": key}

    registered = unauthenticated_client.post(
        "/api/runners/register",
        json=VALID_PAYLOAD,
        headers=headers,
    )
    assert registered.status_code == 201, registered.text

    response = unauthenticated_client.delete(
        f"/api/runners/{VALID_PAYLOAD['username']}",
        headers=headers,
    )

    assert response.status_code == 401


def test_viewer_cannot_delete_runner(client):
    registered = client.post(
        "/api/runners/register",
        json=VALID_PAYLOAD,
        headers={"X-API-Key": _mint(client)},
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


def test_viewer_cannot_mint_or_list_keys(client):
    viewer = User(
        id=56,
        email="key-viewer@example.com",
        full_name="Viewer",
        hashed_password="x",
        role=UserRole.viewer,
        is_active=True,
    )

    async def override_viewer():
        return viewer

    app.dependency_overrides[get_current_user] = override_viewer
    try:
        assert client.post("/api/runners/api-keys", json={"label": "x"}).status_code == 403
        assert client.get("/api/runners/api-keys").status_code == 403
        assert client.delete("/api/runners/api-keys/1").status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_can_delete_runner(client):
    registered = client.post(
        "/api/runners/register",
        json=VALID_PAYLOAD,
        headers={"X-API-Key": _mint(client)},
    )
    assert registered.status_code == 201, registered.text

    response = client.delete(f"/api/runners/{VALID_PAYLOAD['username']}")

    assert response.status_code == 204, response.text
