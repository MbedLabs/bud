"""Artifact quota, lease, and cleanup policy tests."""

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.models import Artifact, UploadAttempt, UploadLease
from app.models.user import User, UserRole
from app.services.artifact_cleanup import reconcile_artifacts
from app.services.artifact_storage import release_upload, reserve_upload


def _admin() -> User:
    return User(
        id=7,
        email="uploader@example.com",
        full_name="Uploader",
        hashed_password="hash",
        role=UserRole.admin,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_run_quota_reserves_only_the_remaining_capacity(db_session, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 25)
    monkeypatch.setattr(settings, "MAX_RUN_UPLOAD_BYTES", 250)
    db_session.add(
        Artifact(
            filename="existing",
            original_filename="existing",
            content_type="text/plain",
            size_bytes=226,
            storage_path="existing",
            test_run_id=1,
        )
    )
    await db_session.commit()

    lease = await reserve_upload(db_session, _admin(), test_run_id=1)

    assert lease.reserved_bytes == 24


@pytest.mark.asyncio
async def test_only_one_active_upload_is_allowed_per_principal(db_session, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 25)
    monkeypatch.setattr(settings, "MAX_RUN_UPLOAD_BYTES", 250)
    first = await reserve_upload(db_session, _admin(), test_run_id=None)

    with pytest.raises(HTTPException) as error:
        await reserve_upload(db_session, _admin(), test_run_id=None)

    assert error.value.status_code == 429
    await release_upload(db_session, first.id)


@pytest.mark.asyncio
async def test_upload_start_rate_is_database_backed(db_session, monkeypatch):
    monkeypatch.setattr(settings, "UPLOADS_PER_15_MINUTES", 2)
    first = await reserve_upload(db_session, _admin(), test_run_id=None)
    await release_upload(db_session, first.id)
    second = await reserve_upload(db_session, _admin(), test_run_id=None)
    await release_upload(db_session, second.id)

    with pytest.raises(HTTPException) as error:
        await reserve_upload(db_session, _admin(), test_run_id=None)

    assert error.value.status_code == 429
    assert "rate" in error.value.detail.lower()


@pytest.mark.asyncio
async def test_reconcile_removes_expired_rows_and_old_orphan_files(
    db_session, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "ARTIFACT_RETENTION_DAYS", 30)
    old = datetime.utcnow() - timedelta(days=31)
    orphan = tmp_path / "orphan.log"
    orphan.write_bytes(b"orphan")
    old_timestamp = (datetime.utcnow() - timedelta(hours=2)).timestamp()
    orphan.touch()
    import os

    os.utime(orphan, (old_timestamp, old_timestamp))
    expired_file = tmp_path / "expired.log"
    expired_file.write_bytes(b"expired")
    db_session.add(
        Artifact(
            filename="expired.log",
            original_filename="expired.log",
            content_type="text/plain",
            size_bytes=7,
            storage_path="expired.log",
            created_at=old,
        )
    )
    db_session.add(
        UploadLease(
            id="expired-lease",
            principal_key="user:99",
            reserved_bytes=25,
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
    )
    db_session.add(
        UploadAttempt(
            principal_key="user:99",
            created_at=datetime.utcnow() - timedelta(minutes=16),
        )
    )
    await db_session.commit()

    report = await reconcile_artifacts(db_session, orphan_grace_seconds=3600)

    assert report.expired_artifacts == 1
    assert report.orphan_files == 1
    assert not expired_file.exists()
    assert not orphan.exists()
    assert await db_session.get(UploadLease, "expired-lease") is None
