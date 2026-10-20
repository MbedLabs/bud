"""
File uploads API endpoints.
"""

import logging
import uuid
from http import HTTPStatus
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_active_entity, get_current_user
from app.core.config import settings
from app.db import get_db
from app.models import Artifact, Runner, TestRun
from app.models.user import User, UserRole
from app.schemas import ArtifactResponse
from app.services import object_store
from app.services.artifact_cleanup import remove_storage_key
from app.services.artifact_storage import (
    persist,
    release_upload,
    reserve_upload,
    store_upload,
    validate_display_metadata,
)
from app.services.audit import record_audit_event

router = APIRouter()

logger = logging.getLogger(__name__)
_UPLOAD_ROOT: Optional[Path] = None


def get_upload_root() -> Path:
    """Return the resolved (canonical) absolute upload root path."""
    global _UPLOAD_ROOT
    if _UPLOAD_ROOT is None:
        _UPLOAD_ROOT = Path(settings.UPLOAD_DIR).resolve()
    return _UPLOAD_ROOT


def ensure_upload_dir() -> Path:
    """Ensure the upload directory exists and return its resolved path."""
    upload_path = get_upload_root()
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


ARTIFACT_DOWNLOAD_HEADERS = {
    "Content-Security-Policy": "sandbox",
    "X-Content-Type-Options": "nosniff",
}


def _can_runner_access_artifact(runner: Runner, artifact: Artifact) -> bool:
    """Runner reads are limited to artifacts associated with its own run."""
    return (
        artifact.test_run is not None
        and artifact.test_run.runner_id is not None
        and artifact.test_run.runner_id == runner.id
    )


def _can_user_delete_artifact(user: User) -> bool:
    """Deleting evidence is fixed to the Admin base role."""
    return user.role == UserRole.admin


async def _get_accessible_artifact(
    db: AsyncSession,
    artifact_id: int,
    current_entity: User | Runner,
) -> Artifact:
    result = await db.execute(
        select(Artifact).options(selectinload(Artifact.test_run)).where(Artifact.id == artifact_id)
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if isinstance(current_entity, Runner) and not _can_runner_access_artifact(
        current_entity, artifact
    ):
        raise HTTPException(status_code=403, detail="Runner is not authorized for this artifact")
    return artifact


async def _validate_runner_upload_run(
    db: AsyncSession, current_entity: User | Runner, run_id: int | None
) -> None:
    """Only a station uploads evidence, and only to one of its own test runs."""
    if isinstance(current_entity, User):
        raise HTTPException(status_code=403, detail="Only stations can upload artifacts")
    if run_id is None:
        if isinstance(current_entity, Runner):
            raise HTTPException(
                status_code=400,
                detail=(
                    "run_id is required: runner uploads must target one of the "
                    "runner's own test runs."
                ),
            )
        return

    test_run = await db.get(TestRun, run_id)
    if test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    if isinstance(current_entity, Runner) and test_run.runner_id != current_entity.id:
        raise HTTPException(
            status_code=403,
            detail="Runner is not authorized to upload artifacts for this test run",
        )


@router.post(
    "",
    response_model=ArtifactResponse,
    status_code=201,
    responses={
        403: {"description": HTTPStatus(403).phrase},
        400: {"description": "Bad Request"},
        404: {"description": "Not Found"},
        415: {"description": "Unsupported Media Type"},
    },
)
async def upload_file(
    file: UploadFile = File(...),
    test_case: Optional[str] = Form(None),
    run_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db, scope="function"),
    _current_entity: User | Runner = Depends(get_current_active_entity),
):
    """Upload a file artifact (trace, log, etc.).

    The content type must be in ALLOWED_UPLOAD_MIME_TYPES. The file is stored inside the
    upload root under a UUID name, keeping the client's extension only when it is a dot and
    at most nine letters or digits; the artifact records that relative key, and the client's
    file name only for display.
    """
    await _validate_runner_upload_run(db, _current_entity, run_id)
    display_filename = validate_display_metadata(file.filename, test_case)

    content_type = file.content_type or "application/octet-stream"
    if content_type not in settings.ALLOWED_UPLOAD_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported media type '{content_type}'. "
                f"Allowed types: {', '.join(settings.ALLOWED_UPLOAD_MIME_TYPES)}"
            ),
        )

    ext = ""
    if file.filename:
        suffix = Path(file.filename).suffix
        if suffix and suffix[1:].isalnum() and len(suffix) <= 10:
            ext = suffix.lower()

    unique_filename = f"{uuid.uuid4()}{ext}"

    upload_dir = ensure_upload_dir()
    storage_path = upload_dir / unique_filename

    resolved_storage = storage_path.resolve()
    if resolved_storage.parent != upload_dir:
        raise HTTPException(status_code=400, detail="Invalid file path.")

    lease = await reserve_upload(db, _current_entity, test_run_id=run_id)
    lease_id = lease.id
    try:
        stored = await store_upload(file, resolved_storage, max_bytes=lease.reserved_bytes)
        await persist(resolved_storage, unique_filename, content_type)

        artifact = Artifact(
            filename=unique_filename,
            original_filename=display_filename,
            content_type=content_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            storage_path=unique_filename,
            test_case=test_case,
            test_run_id=run_id,
        )
        db.add(artifact)
        await db.flush()
        await record_audit_event(
            db,
            "artifact.uploaded",
            target_type="test_run",
            target_id=run_id,
            details={
                "artifact_id": artifact.id,
                "filename": display_filename,
                "size": stored.size_bytes,
                "station": getattr(_current_entity, "account", None),
            },
        )
        await db.delete(lease)
        await db.commit()
        await db.refresh(artifact)
    except BaseException:
        await db.rollback()
        if resolved_storage.exists():
            resolved_storage.unlink()
        await release_upload(db, lease_id)
        raise

    return artifact


@router.get(
    "/{artifact_id}",
    responses={
        503: {"description": HTTPStatus(503).phrase},
        400: {"description": "Bad Request"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
    },
)
async def download_artifact(
    artifact_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _current_entity: User | Runner = Depends(get_current_active_entity),
):
    """
    Download an artifact by ID.

    The path is rebuilt from the upload root and the stored key and has to resolve inside
    the upload root. An artifact is user-supplied (an HTML report, an SVG plot): it
    downloads as an attachment with ARTIFACT_DOWNLOAD_HEADERS, and a browser that renders it
    anyway renders it sandboxed, without script and without access to the Bud origin.
    """
    artifact = await _get_accessible_artifact(db, artifact_id, _current_entity)

    upload_root = get_upload_root()
    storage_path = (upload_root / artifact.storage_path).resolve()

    if storage_path.parent != upload_root:
        raise HTTPException(status_code=400, detail="Invalid artifact path.")

    if object_store.s3_enabled():
        try:
            body = await object_store.fetch(artifact.storage_path)
            name = artifact.original_filename
            return StreamingResponse(
                object_store.iter_body(body),
                media_type=artifact.content_type,
                headers={
                    **ARTIFACT_DOWNLOAD_HEADERS,
                    "Content-Disposition": (
                        f"attachment; filename=\"{name}\"; filename*=UTF-8''{quote(name)}"
                    ),
                },
            )
        except Exception as exc:
            if not (object_store.keeps_local_copy() and storage_path.exists()):
                raise HTTPException(status_code=503, detail="The file store is unreachable.")
            logger.warning(
                "Object storage read failed for %s; serving the local mirror: %s",
                object_store.object_key(artifact.storage_path),
                exc,
            )

    if not storage_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(storage_path),
        filename=artifact.original_filename,
        media_type=artifact.content_type,
        headers=ARTIFACT_DOWNLOAD_HEADERS,
    )


@router.get(
    "/info/{artifact_id}",
    response_model=ArtifactResponse,
    responses={403: {"description": "Forbidden"}, 404: {"description": "Not Found"}},
)
async def get_artifact_info(
    artifact_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _current_entity: User | Runner = Depends(get_current_active_entity),
):
    """
    Get artifact metadata without downloading.
    """
    return await _get_accessible_artifact(db, artifact_id, _current_entity)


@router.delete(
    "/{artifact_id}",
    status_code=204,
    responses={403: {"description": "Forbidden"}, 404: {"description": "Not Found"}},
)
async def delete_artifact(
    artifact_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _current_user: User = Depends(get_current_user),
):
    """
    Delete an artifact.
    """
    result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    artifact = result.scalar_one_or_none()

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    if not _can_user_delete_artifact(_current_user):
        raise HTTPException(status_code=403, detail="Only admins may delete artifacts")

    storage_key = artifact.storage_path
    await record_audit_event(
        db,
        "artifact.deleted",
        target_type="test_run",
        target_id=artifact.test_run_id,
        details={"artifact_id": artifact.id, "filename": artifact.original_filename},
    )
    await db.delete(artifact)
    await db.commit()
    await remove_storage_key(storage_key)
