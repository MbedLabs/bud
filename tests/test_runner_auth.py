"""
Runner JWT auth: expired tokens accepted only with a recent heartbeat.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-at-least-32-characters-long")

from app.api.auth import get_current_active_entity  # noqa: E402
from app.api.results import get_uploader_entity  # noqa: E402
from app.core.runner_auth import (  # noqa: E402
    authenticate_runner_token,
    authenticate_teststation_token,
    decode_access_token_ignore_exp,
    runner_has_recent_heartbeat,
)
from app.core.security import create_access_token, decode_access_token  # noqa: E402
from app.models import Runner, TestStation  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.schemas import ResultsUpload  # noqa: E402


def test_decode_access_token_ignore_exp_reads_expired_runner_claims():
    token = create_access_token(
        {"sub": "runner-expired", "type": "runner"},
        expires_delta=timedelta(seconds=-1),
    )
    assert decode_access_token(token) is None
    payload = decode_access_token_ignore_exp(token)
    assert payload is not None
    assert payload["sub"] == "runner-expired"
    assert payload["type"] == "runner"


@pytest.mark.asyncio
async def test_authenticate_runner_token_rejects_expired_without_heartbeat(db_session):
    token = create_access_token(
        {"sub": "runner-stale", "type": "runner"},
        expires_delta=timedelta(seconds=-1),
    )
    runner = Runner(
        account="runner-stale",
        password_hash="x",
        token=token,
        is_active=True,
        last_heartbeat=None,
    )
    db_session.add(runner)
    await db_session.commit()

    assert await authenticate_runner_token(token, db_session) is None


@pytest.mark.asyncio
async def test_authenticate_runner_token_accepts_expired_with_recent_heartbeat(db_session):
    token = create_access_token(
        {"sub": "runner-live", "type": "runner"},
        expires_delta=timedelta(seconds=-1),
    )
    runner = Runner(
        account="runner-live",
        password_hash="x",
        token=token,
        is_active=True,
        last_heartbeat=datetime.utcnow(),
    )
    db_session.add(runner)
    await db_session.commit()

    authed = await authenticate_runner_token(token, db_session)
    assert authed is not None
    assert authed.account == "runner-live"


@pytest.mark.asyncio
async def test_get_uploader_entity_accepts_expired_runner_jwt(db_session):
    from app.api.results import get_uploader_entity

    token = create_access_token(
        {"sub": "uploader-runner", "type": "runner"},
        expires_delta=timedelta(seconds=-1),
    )
    runner = Runner(
        account="uploader-runner",
        password_hash="x",
        token=token,
        is_active=True,
        last_heartbeat=datetime.utcnow(),
    )
    db_session.add(runner)
    await db_session.commit()

    entity = await get_uploader_entity(
        ResultsUpload(results=[]),
        db=db_session,
        token=token,
        x_api_key=None,
    )
    assert isinstance(entity, Runner)
    assert entity.account == "uploader-runner"


@pytest.mark.asyncio
async def test_get_uploader_entity_accepts_api_key_and_runner_account(db_session):
    runner = Runner(
        account="api-key-runner",
        password_hash="x",
        token="stored-runner-token",
        is_active=True,
    )
    db_session.add(runner)
    await db_session.commit()

    entity = await get_uploader_entity(
        ResultsUpload(results=[], runner_account=runner.account),
        db=db_session,
        token=None,
        x_api_key="test-runner-api-key",
    )

    assert isinstance(entity, Runner)
    assert entity.account == runner.account


@pytest.mark.asyncio
async def test_runner_token_rotation_invalidates_previous_token(db_session):
    old_token = create_access_token({"sub": "runner-rotated", "type": "runner"})
    current_token = create_access_token({"sub": "runner-rotated", "type": "runner", "jti": "new"})
    runner = Runner(
        account="runner-rotated",
        password_hash="x",
        token=current_token,
        is_active=True,
        last_heartbeat=datetime.utcnow(),
    )
    db_session.add(runner)
    await db_session.commit()

    assert await authenticate_runner_token(old_token, db_session) is None
    assert await authenticate_runner_token(current_token, db_session) is not None


@pytest.mark.asyncio
async def test_teststation_expired_current_token_uses_recent_heartbeat(db_session):
    token = create_access_token(
        {"sub": "station-live", "type": "teststation"},
        expires_delta=timedelta(seconds=-1),
    )
    station = TestStation(
        account="station-live",
        password_hash="x",
        token=token,
        is_active=True,
        last_heartbeat=datetime.utcnow(),
    )
    db_session.add(station)
    await db_session.commit()

    assert await authenticate_teststation_token(token, db_session) is not None


@pytest.mark.asyncio
async def test_runner_has_recent_heartbeat_respects_timeout(monkeypatch):
    monkeypatch.setattr("app.core.runner_auth.settings.RUNNER_HEARTBEAT_TIMEOUT", 60)
    runner = Runner(
        account="hb",
        password_hash="x",
        token="hb-token",
        last_heartbeat=datetime.utcnow() - timedelta(seconds=90),
    )
    assert runner_has_recent_heartbeat(runner) is False
    runner.last_heartbeat = datetime.utcnow()
    assert runner_has_recent_heartbeat(runner) is True


@pytest.mark.asyncio
async def test_teststation_token_cannot_resolve_as_numeric_user(db_session):
    user = User(
        id=1,
        email="admin@example.com",
        full_name="Admin",
        hashed_password="x",
        role=UserRole.admin,
        is_active=True,
    )
    station = TestStation(
        account="001",
        password_hash="x",
        token="stored-token",
        is_active=True,
    )
    db_session.add_all([user, station])
    await db_session.commit()

    token = create_access_token({"sub": "001", "type": "teststation"})

    with pytest.raises(HTTPException) as entity_error:
        await get_current_active_entity(token=token, db=db_session)
    assert entity_error.value.status_code == 401

    with pytest.raises(HTTPException) as upload_error:
        await get_uploader_entity(
            ResultsUpload(results=[]),
            db=db_session,
            token=token,
            x_api_key=None,
        )
    assert upload_error.value.status_code == 401


@pytest.mark.asyncio
async def test_token_without_explicit_type_is_rejected(db_session):
    user = User(
        id=2,
        email="viewer@example.com",
        full_name="Viewer",
        hashed_password="x",
        role=UserRole.viewer,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token({"sub": str(user.id)})

    with pytest.raises(HTTPException) as error:
        await get_current_active_entity(token=token, db=db_session)
    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_stale_user_token_cannot_upload_results(unauthenticated_client, db_session):
    user = User(
        email="stale-uploader@example.com",
        full_name="Stale Uploader",
        hashed_password="x",
        role=UserRole.admin,
        is_active=True,
        session_version=2,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    stale_token = create_access_token({"sub": str(user.id), "type": "user", "ver": 1})
    response = unauthenticated_client.post(
        "/api/results",
        json={"results": []},
        headers={"Authorization": f"Bearer {stale_token}"},
    )

    assert response.status_code == 401
    assert "Authentication required" in response.json()["detail"]
