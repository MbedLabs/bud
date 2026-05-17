"""
Runner JWT auth: expired tokens accepted only with a recent heartbeat.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-at-least-32-characters-long")

from app.core.runner_auth import (  # noqa: E402
    authenticate_runner_token,
    decode_access_token_ignore_exp,
    runner_has_recent_heartbeat,
)
from app.core.security import create_access_token, decode_access_token  # noqa: E402
from app.models import Runner  # noqa: E402
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
    runner = Runner(
        account="runner-stale",
        password_hash="x",
        token="stale-token",
        is_active=True,
        last_heartbeat=None,
    )
    db_session.add(runner)
    await db_session.commit()

    token = create_access_token(
        {"sub": "runner-stale", "type": "runner"},
        expires_delta=timedelta(seconds=-1),
    )
    assert await authenticate_runner_token(token, db_session) is None


@pytest.mark.asyncio
async def test_authenticate_runner_token_accepts_expired_with_recent_heartbeat(db_session):
    runner = Runner(
        account="runner-live",
        password_hash="x",
        token="live-token",
        is_active=True,
        last_heartbeat=datetime.utcnow(),
    )
    db_session.add(runner)
    await db_session.commit()

    token = create_access_token(
        {"sub": "runner-live", "type": "runner"},
        expires_delta=timedelta(seconds=-1),
    )
    authed = await authenticate_runner_token(token, db_session)
    assert authed is not None
    assert authed.account == "runner-live"


@pytest.mark.asyncio
async def test_get_uploader_entity_accepts_expired_runner_jwt(db_session):
    from app.api.results import get_uploader_entity

    runner = Runner(
        account="uploader-runner",
        password_hash="x",
        token="upload-token",
        is_active=True,
        last_heartbeat=datetime.utcnow(),
    )
    db_session.add(runner)
    await db_session.commit()

    token = create_access_token(
        {"sub": "uploader-runner", "type": "runner"},
        expires_delta=timedelta(seconds=-1),
    )
    entity = await get_uploader_entity(
        ResultsUpload(results=[]),
        db=db_session,
        token=token,
        x_api_key=None,
    )
    assert isinstance(entity, Runner)
    assert entity.account == "uploader-runner"


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
