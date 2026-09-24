"""Retention and orphan reconciliation for Bud's artifact volume."""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Artifact, UploadAttempt, UploadLease
from app.services import object_store


@dataclass(frozen=True)
class CleanupReport:
    expired_artifacts: int = 0
    orphan_files: int = 0
    missing_files: int = 0
    leader_acquired: bool = True


def _safe_upload_root() -> Path:
    root = Path(settings.UPLOAD_DIR).resolve()
    if root == Path(root.anchor) or root == Path.home().resolve():
        raise RuntimeError("Refusing artifact cleanup for an unsafe upload root.")
    root.mkdir(parents=True, exist_ok=True)
    return root


async def reconcile_artifacts(
    db: AsyncSession, *, orphan_grace_seconds: int = 3600
) -> CleanupReport:
    """Remove expired rows/files and old unreferenced files under the upload root.

    With S3 storage the bucket is reconciled (a file is missing when the bucket lacks
    it), and the local mirror, when kept, is cleared of orphans too.
    """

    now = datetime.utcnow()
    root = _safe_upload_root()
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        acquired = await db.scalar(select(func.pg_try_advisory_xact_lock(1730554202)))
        if not acquired:
            await db.rollback()
            return CleanupReport(leader_acquired=False)
    retention_cutoff = now - timedelta(days=settings.ARTIFACT_RETENTION_DAYS)
    expired = list(
        (await db.scalars(select(Artifact).where(Artifact.created_at < retention_cutoff))).all()
    )
    expired_count = 0
    for artifact in expired:
        await remove_storage_key(artifact.storage_path)
        await db.delete(artifact)
        expired_count += 1
    await db.flush()

    referenced = set((await db.scalars(select(Artifact.storage_path))).all())
    orphan_cutoff = time.time() - orphan_grace_seconds
    orphan_count = 0
    if object_store.keeps_local_copy():
        for path in root.iterdir():
            if (
                path.is_file()
                and path.name not in referenced
                and path.stat().st_mtime < orphan_cutoff
            ):
                with contextlib.suppress(OSError):
                    path.unlink()
                    orphan_count += 1

    if object_store.s3_enabled():
        cutoff = datetime.fromtimestamp(orphan_cutoff, tz=timezone.utc)
        present = set()
        for stored in await object_store.list_objects():
            present.add(stored.name)
            if stored.name not in referenced and stored.last_modified < cutoff:
                await object_store.delete(stored.name)
                orphan_count += 1
        missing_count = len(referenced - present)
    else:
        missing_count = sum(1 for storage_key in referenced if not (root / storage_key).is_file())
    await db.execute(delete(UploadLease).where(UploadLease.expires_at <= now))
    await db.execute(
        delete(UploadAttempt).where(UploadAttempt.created_at < now - timedelta(minutes=15))
    )
    await db.commit()
    return CleanupReport(
        expired_artifacts=expired_count,
        orphan_files=orphan_count,
        missing_files=missing_count,
    )


def unlink_storage_key(storage_key: str) -> None:
    """Best-effort deletion restricted to a direct child of the upload root."""

    root = _safe_upload_root()
    path = (root / storage_key).resolve()
    if path.parent == root:
        with contextlib.suppress(OSError):
            path.unlink()


async def remove_storage_key(storage_key: str) -> None:
    """Delete a stored file wherever it is kept; a missing file is not an error."""
    unlink_storage_key(storage_key)
    if object_store.s3_enabled():
        with contextlib.suppress(Exception):
            await object_store.delete(storage_key)
