from datetime import datetime

import pytest

from app.models import Artifact, Runner, TestRun
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_runner_heartbeat_wrong_account_returns_403(client, db_session):
    runner = Runner(
        account="runner-a",
        password_hash="hash",
        token="runner-token",
        socket_port=53035,
    )
    db_session.add(runner)
    await db_session.commit()
    await db_session.refresh(runner)

    from app.core.deps import get_current_runner
    from app.main import app

    async def override_get_current_runner():
        return runner

    app.dependency_overrides[get_current_runner] = override_get_current_runner
    try:
        response = client.post(
            "/api/runners/heartbeat",
            json={"runner_account": "runner-b", "location": "lab"},
        )
    finally:
        app.dependency_overrides.pop(get_current_runner, None)

    assert response.status_code == 403
    assert "own runner account" in response.json()["detail"]


@pytest.mark.asyncio
async def test_runner_cannot_download_unowned_artifact(client, db_session, test_user):
    owner_runner = Runner(
        account="owner-runner",
        password_hash="hash",
        token="owner-token",
        socket_port=53035,
    )
    other_runner = Runner(
        account="other-runner",
        password_hash="hash",
        token="other-token",
        socket_port=53036,
    )
    db_session.add_all([owner_runner, other_runner])
    await db_session.flush()

    test_run = TestRun(
        name="run-1",
        status="Completed",
        started_at=datetime.utcnow(),
        runner_id=owner_runner.id,
        created_by=test_user.id,
    )
    db_session.add(test_run)
    await db_session.flush()

    artifact = Artifact(
        filename="artifact.txt",
        original_filename="artifact.txt",
        content_type="text/plain",
        size_bytes=4,
        storage_path="artifact.txt",
        test_run_id=test_run.id,
    )
    db_session.add(artifact)
    await db_session.commit()

    from app.api.auth import get_current_active_entity
    from app.api.results import get_uploader_entity
    from app.main import app

    async def override_entity():
        return other_runner

    app.dependency_overrides[get_current_active_entity] = override_entity
    app.dependency_overrides[get_uploader_entity] = override_entity
    try:
        response = client.get(f"/api/uploads/info/{artifact.id}")
    finally:
        app.dependency_overrides.pop(get_current_active_entity, None)
        app.dependency_overrides.pop(get_uploader_entity, None)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_runner_can_read_owned_artifact_info(client, db_session, test_user):
    owner_runner = Runner(
        account="owner-runner",
        password_hash="hash",
        token="owner-token",
        socket_port=53035,
    )
    db_session.add(owner_runner)
    await db_session.flush()

    test_run = TestRun(
        name="run-1",
        status="Completed",
        started_at=datetime.utcnow(),
        runner_id=owner_runner.id,
        created_by=test_user.id,
    )
    db_session.add(test_run)
    await db_session.flush()

    artifact = Artifact(
        filename="artifact.txt",
        original_filename="artifact.txt",
        content_type="text/plain",
        size_bytes=4,
        storage_path="artifact.txt",
        test_run_id=test_run.id,
    )
    db_session.add(artifact)
    await db_session.commit()

    from app.api.auth import get_current_active_entity
    from app.api.results import get_uploader_entity
    from app.main import app

    async def override_entity():
        return owner_runner

    app.dependency_overrides[get_current_active_entity] = override_entity
    app.dependency_overrides[get_uploader_entity] = override_entity
    try:
        response = client.get(f"/api/uploads/info/{artifact.id}")
    finally:
        app.dependency_overrides.pop(get_current_active_entity, None)
        app.dependency_overrides.pop(get_uploader_entity, None)

    assert response.status_code == 200
    assert response.json()["id"] == artifact.id


@pytest.mark.asyncio
async def test_non_admin_cannot_delete_artifact(client, db_session):
    user = User(
        id=2,
        email="maintainer@example.com",
        full_name="Maintainer",
        hashed_password="hash",
        role=UserRole.maintainer,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    artifact = Artifact(
        filename="artifact.txt",
        original_filename="artifact.txt",
        content_type="text/plain",
        size_bytes=4,
        storage_path="artifact.txt",
    )
    db_session.add(artifact)
    await db_session.commit()

    from app.api.auth import get_current_user
    from app.main import app

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user
    try:
        response = client.delete(f"/api/uploads/{artifact.id}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403
    assert "Only admins" in response.json()["detail"]
