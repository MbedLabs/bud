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
async def test_runner_cannot_download_unowned_artifact(client, db_session):
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
        test_case_list="[]",
        status="Completed",
        started_at=datetime.utcnow(),
        runner_id=owner_runner.id,
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
async def test_runner_can_read_owned_artifact_info(client, db_session):
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
        test_case_list="[]",
        status="Completed",
        started_at=datetime.utcnow(),
        runner_id=owner_runner.id,
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
        role=UserRole.viewer,
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


@pytest.mark.asyncio
async def test_runner_cannot_upload_artifact_to_another_runners_run(client, db_session):
    owner_runner = Runner(
        account="owner-upload-runner",
        password_hash="hash",
        token="owner-upload-token",
        socket_port=53035,
    )
    other_runner = Runner(
        account="other-upload-runner",
        password_hash="hash",
        token="other-upload-token",
        socket_port=53036,
    )
    db_session.add_all([owner_runner, other_runner])
    await db_session.flush()

    test_run = TestRun(
        name="owned-run",
        test_case_list="[]",
        status="Running",
        started_at=datetime.utcnow(),
        runner_id=owner_runner.id,
    )
    db_session.add(test_run)
    await db_session.commit()

    from app.api.auth import get_current_active_entity
    from app.main import app

    async def override_entity():
        return other_runner

    app.dependency_overrides[get_current_active_entity] = override_entity
    try:
        response = client.post(
            "/api/uploads",
            files={"file": ("artifact.txt", b"data", "text/plain")},
            data={"run_id": str(test_run.id)},
        )
    finally:
        app.dependency_overrides.pop(get_current_active_entity, None)

    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"]


@pytest.mark.asyncio
async def test_runner_can_upload_artifact_to_owned_run(client, db_session):
    runner = Runner(
        account="owned-upload-runner",
        password_hash="hash",
        token="owned-upload-token",
        socket_port=53035,
    )
    db_session.add(runner)
    await db_session.flush()

    test_run = TestRun(
        name="owned-run",
        test_case_list="[]",
        status="Running",
        started_at=datetime.utcnow(),
        runner_id=runner.id,
    )
    db_session.add(test_run)
    await db_session.commit()

    from app.api.auth import get_current_active_entity
    from app.main import app

    async def override_entity():
        return runner

    app.dependency_overrides[get_current_active_entity] = override_entity
    try:
        response = client.post(
            "/api/uploads",
            files={"file": ("artifact.txt", b"data", "text/plain")},
            data={"run_id": str(test_run.id)},
        )
    finally:
        app.dependency_overrides.pop(get_current_active_entity, None)

    assert response.status_code == 201
    assert response.json()["test_run_id"] == test_run.id


@pytest.mark.asyncio
async def test_runner_upload_with_unknown_run_returns_404(client, db_session):
    runner = Runner(
        account="missing-run-upload-runner",
        password_hash="hash",
        token="missing-run-upload-token",
        socket_port=53035,
    )
    db_session.add(runner)
    await db_session.commit()

    from app.api.auth import get_current_active_entity
    from app.main import app

    async def override_entity():
        return runner

    app.dependency_overrides[get_current_active_entity] = override_entity
    try:
        response = client.post(
            "/api/uploads",
            files={"file": ("artifact.txt", b"data", "text/plain")},
            data={"run_id": "999999"},
        )
    finally:
        app.dependency_overrides.pop(get_current_active_entity, None)

    assert response.status_code == 404
    assert "Test run not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_oversized_upload_streams_to_413_and_leaves_no_partial_file(
    client, db_session, monkeypatch
):
    """The streamed upload path must reject past-cap bodies with 413 and clean up."""
    import app.api.uploads as uploads_module
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "MAX_UPLOAD_SIZE", 10)  # tiny cap for the test

    upload_root = uploads_module.get_upload_root()
    before = set(upload_root.glob("*")) if upload_root.exists() else set()

    response = client.post(
        "/api/uploads",
        files={"file": ("too-big.txt", b"x" * 64, "text/plain")},
    )

    assert response.status_code == 413
    assert "File too large" in response.json()["detail"]
    after = set(upload_root.glob("*")) if upload_root.exists() else set()
    assert after == before  # no partial file left behind


@pytest.mark.asyncio
async def test_upload_at_exact_file_limit_is_accepted(client, monkeypatch):
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "MAX_UPLOAD_SIZE", 10)
    monkeypatch.setattr(app_settings, "MIN_UPLOAD_FREE_BYTES", 0)

    response = client.post(
        "/api/uploads",
        files={"file": ("at-limit.txt", b"x" * 10, "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["size_bytes"] == 10


@pytest.mark.asyncio
async def test_upload_rejects_invalid_display_metadata_before_writing(client):
    response = client.post(
        "/api/uploads",
        files={"file": (("x" * 256) + ".txt", b"safe", "text/plain")},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_rejects_when_free_space_reserve_cannot_be_preserved(
    client, monkeypatch
):
    import app.services.artifact_storage as storage_module
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "MIN_UPLOAD_FREE_BYTES", 1024)
    monkeypatch.setattr(
        storage_module.shutil,
        "disk_usage",
        lambda _path: type("Usage", (), {"free": 1024})(),
    )

    response = client.post(
        "/api/uploads",
        files={"file": ("trace.txt", b"data", "text/plain")},
    )

    assert response.status_code == 507
    assert "free space" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_endpoint_uses_remaining_per_run_capacity(
    client, db_session, monkeypatch, tmp_path
):
    import app.api.uploads as uploads_module
    from app.core.config import settings as app_settings

    monkeypatch.setattr(uploads_module, "_UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr(app_settings, "MIN_UPLOAD_FREE_BYTES", 0)
    monkeypatch.setattr(app_settings, "MAX_UPLOAD_SIZE", 25)
    monkeypatch.setattr(app_settings, "MAX_RUN_UPLOAD_BYTES", 250)
    run = TestRun(name="quota-run", test_case_list="[]", status="Running")
    db_session.add(run)
    await db_session.flush()
    db_session.add(
        Artifact(
            filename="existing",
            original_filename="existing",
            content_type="text/plain",
            size_bytes=249,
            storage_path="existing",
            test_run_id=run.id,
        )
    )
    await db_session.commit()

    response = client.post(
        "/api/uploads",
        files={"file": ("trace.txt", b"x", "text/plain")},
        data={"run_id": str(run.id)},
    )

    assert response.status_code == 201, response.text
    assert response.json()["size_bytes"] == 1


@pytest.mark.asyncio
async def test_upload_endpoint_rejects_bytes_beyond_remaining_run_capacity(
    client, db_session, monkeypatch, tmp_path
):
    import app.api.uploads as uploads_module
    from app.core.config import settings as app_settings

    monkeypatch.setattr(uploads_module, "_UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr(app_settings, "MIN_UPLOAD_FREE_BYTES", 0)
    monkeypatch.setattr(app_settings, "MAX_UPLOAD_SIZE", 25)
    monkeypatch.setattr(app_settings, "MAX_RUN_UPLOAD_BYTES", 250)
    run = TestRun(name="quota-overflow", test_case_list="[]", status="Running")
    db_session.add(run)
    await db_session.flush()
    db_session.add(
        Artifact(
            filename="existing",
            original_filename="existing",
            content_type="text/plain",
            size_bytes=249,
            storage_path="existing",
            test_run_id=run.id,
        )
    )
    await db_session.commit()

    response = client.post(
        "/api/uploads",
        files={"file": ("trace.txt", b"xx", "text/plain")},
        data={"run_id": str(run.id)},
    )

    assert response.status_code == 413
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_viewer_cannot_upload_artifacts(client):
    from app.api.auth import get_current_active_entity
    from app.main import app

    viewer = User(
        id=88,
        email="viewer-upload@example.com",
        full_name="Viewer",
        hashed_password="hash",
        role=UserRole.viewer,
        is_active=True,
    )

    async def override_viewer():
        return viewer

    app.dependency_overrides[get_current_active_entity] = override_viewer
    try:
        response = client.post(
            "/api/uploads",
            files={"file": ("trace.txt", b"x", "text/plain")},
        )
    finally:
        app.dependency_overrides.pop(get_current_active_entity, None)

    assert response.status_code == 403
