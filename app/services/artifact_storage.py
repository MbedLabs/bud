"""Bounded, atomic filesystem writes for uploaded artifacts."""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Artifact, Runner, UploadAttempt, UploadLease
from app.models.user import User


@dataclass(frozen=True)
class StoredUpload:
    size_bytes: int
    sha256: str


def upload_principal_key(entity: User | Runner) -> str:
    kind = "runner" if isinstance(entity, Runner) else "user"
    return f"{kind}:{entity.id}"


def _advisory_key(value: str) -> int:
    raw = hashlib.sha256(value.encode("utf-8")).digest()[:8]
    return int.from_bytes(raw, byteorder="big", signed=True)


async def _lock_policy_key(db: AsyncSession, value: str) -> None:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        await db.execute(select(func.pg_advisory_xact_lock(_advisory_key(value))))


async def reserve_upload(
    db: AsyncSession,
    entity: User | Runner,
    *,
    test_run_id: int | None,
) -> UploadLease:
    """Atomically enforce rate, concurrency, and per-run reservation limits."""

    now = datetime.utcnow()
    window_start = now - timedelta(minutes=15)
    principal = upload_principal_key(entity)
    reservation_bytes = settings.MAX_UPLOAD_SIZE
    await _lock_policy_key(db, f"upload-principal:{principal}")
    await db.execute(delete(UploadLease).where(UploadLease.expires_at <= now))
    await db.execute(delete(UploadAttempt).where(UploadAttempt.created_at < window_start))

    attempts = await db.scalar(
        select(func.count(UploadAttempt.id)).where(
            UploadAttempt.principal_key == principal,
            UploadAttempt.created_at >= window_start,
        )
    )
    if (attempts or 0) >= settings.UPLOADS_PER_15_MINUTES:
        await db.rollback()
        raise HTTPException(
            status_code=429,
            detail="Upload rate limit exceeded; retry after the 15-minute window.",
            headers={"Retry-After": "900"},
        )

    active = await db.scalar(
        select(UploadLease.id).where(
            UploadLease.principal_key == principal,
            UploadLease.expires_at > now,
        )
    )
    if active is not None:
        db.add(UploadAttempt(principal_key=principal, created_at=now))
        await db.commit()
        raise HTTPException(
            status_code=429,
            detail="An upload is already active for this account.",
            headers={"Retry-After": "60"},
        )

    if test_run_id is not None:
        await _lock_policy_key(db, f"upload-run:{test_run_id}")
        committed = await db.scalar(
            select(func.coalesce(func.sum(Artifact.size_bytes), 0)).where(
                Artifact.test_run_id == test_run_id
            )
        )
        reserved = await db.scalar(
            select(func.coalesce(func.sum(UploadLease.reserved_bytes), 0)).where(
                UploadLease.test_run_id == test_run_id,
                UploadLease.expires_at > now,
            )
        )
        available = settings.MAX_RUN_UPLOAD_BYTES - (committed or 0) - (reserved or 0)
        if available <= 0:
            db.add(UploadAttempt(principal_key=principal, created_at=now))
            await db.commit()
            raise HTTPException(
                status_code=413,
                detail=(
                    "Run artifact quota exceeded. Maximum aggregate size is "
                    f"{settings.MAX_RUN_UPLOAD_BYTES} bytes."
                ),
            )
        reservation_bytes = min(settings.MAX_UPLOAD_SIZE, available)

    lease = UploadLease(
        id=str(uuid.uuid4()),
        principal_key=principal,
        test_run_id=test_run_id,
        reserved_bytes=reservation_bytes,
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    db.add(UploadAttempt(principal_key=principal, created_at=now))
    db.add(lease)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=429,
            detail="An upload is already active for this account.",
            headers={"Retry-After": "60"},
        ) from exc
    await db.refresh(lease)
    return lease


async def release_upload(db: AsyncSession, lease_id: str) -> None:
    await db.execute(delete(UploadLease).where(UploadLease.id == lease_id))
    await db.commit()


def validate_display_metadata(filename: str | None, test_case: str | None) -> str:
    """Validate values retained for display/DB storage; neither becomes a path."""

    display_name = filename or "unknown"
    if len(display_name) > 255 or any(ord(char) < 32 for char in display_name):
        raise HTTPException(status_code=422, detail="Invalid upload filename.")
    if test_case is not None and (
        len(test_case) > 255 or any(ord(char) < 32 for char in test_case)
    ):
        raise HTTPException(status_code=422, detail="Invalid test-case metadata.")
    return display_name


def ensure_free_space(upload_root: Path, remaining_write_bytes: int) -> None:
    """Preserve the configured disk reserve throughout a streamed write."""

    free_bytes = shutil.disk_usage(upload_root).free
    required = settings.MIN_UPLOAD_FREE_BYTES + max(0, remaining_write_bytes)
    if free_bytes < required:
        raise HTTPException(
            status_code=507,
            detail="Insufficient free space to accept this upload safely.",
        )


async def store_upload(
    file: UploadFile, final_path: Path, *, max_bytes: int | None = None
) -> StoredUpload:
    """Stream an upload to a temporary file and atomically promote it."""

    byte_limit = settings.MAX_UPLOAD_SIZE if max_bytes is None else max_bytes
    temp_path = final_path.parent / f".upload-{uuid.uuid4().hex}.part"
    size_bytes = 0
    digest = hashlib.sha256()
    ensure_free_space(final_path.parent, byte_limit)

    try:
        async with aiofiles.open(temp_path, "xb") as output:
            while chunk := await file.read(settings.UPLOAD_STREAM_CHUNK_BYTES):
                size_bytes += len(chunk)
                if size_bytes > byte_limit:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Available upload limit is {byte_limit} bytes.",
                    )
                ensure_free_space(final_path.parent, byte_limit - size_bytes)
                digest.update(chunk)
                await output.write(chunk)
        os.replace(temp_path, final_path)
    except BaseException:
        for path in (temp_path, final_path):
            with contextlib.suppress(OSError):
                path.unlink()
        raise

    return StoredUpload(size_bytes=size_bytes, sha256=digest.hexdigest())
