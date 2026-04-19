"""
File uploads API endpoints.
"""

import os
import uuid
from pathlib import Path
from typing import Optional, Union

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_active_entity, get_current_user
from app.core.config import settings
from app.db import get_db
from app.models import Artifact, Runner
from app.models.user import User
from app.schemas import ArtifactResponse

router = APIRouter()

# Resolved absolute upload root — used for path-traversal checks (C3)
_UPLOAD_ROOT: Optional[Path] = None


def get_upload_root() -> Path:
    """Return the resolved (canonical) absolute upload root path."""
    global _UPLOAD_ROOT
    if _UPLOAD_ROOT is None:
        _UPLOAD_ROOT = Path(settings.UPLOAD_DIR).resolve()
    return _UPLOAD_ROOT


async def ensure_upload_dir() -> Path:
    """Ensure the upload directory exists and return its resolved path."""
    upload_path = get_upload_root()
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


@router.post("", response_model=ArtifactResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    test_case: Optional[str] = Form(None),
    run_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """
    Upload a file artifact (trace, log, etc.).

    Files are stored with a UUID filename and can be associated with
    a test case and/or test run.
    """
    # H4: Validate MIME type against allowlist
    content_type = file.content_type or "application/octet-stream"
    if content_type not in settings.ALLOWED_UPLOAD_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported media type '{content_type}'. "
                f"Allowed types: {', '.join(settings.ALLOWED_UPLOAD_MIME_TYPES)}"
            ),
        )

    # Check file size
    content = await file.read()
    file_size = len(content)

    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE} bytes",
        )

    # Generate a UUID-only filename — never use the client-supplied filename
    # as part of the storage path (C3: prevents path traversal / directory injection)
    ext = ""
    if file.filename:
        suffix = Path(file.filename).suffix
        # Only allow simple alphanumeric extensions to avoid tricks like ".php\0.txt"
        if suffix and suffix[1:].isalnum() and len(suffix) <= 10:
            ext = suffix.lower()

    unique_filename = f"{uuid.uuid4()}{ext}"

    # Save file
    upload_dir = await ensure_upload_dir()
    storage_path = upload_dir / unique_filename

    # C3: Verify the resolved storage path is still inside the upload root
    resolved_storage = storage_path.resolve()
    if not str(resolved_storage).startswith(str(upload_dir)):
        raise HTTPException(status_code=400, detail="Invalid file path.")

    async with aiofiles.open(resolved_storage, "wb") as f:
        await f.write(content)

    # Create database record — store only the relative filename, not the full path
    artifact = Artifact(
        filename=unique_filename,
        original_filename=file.filename or "unknown",
        content_type=content_type,
        size_bytes=file_size,
        storage_path=unique_filename,  # relative to UPLOAD_DIR; never store full FS path
        test_case=test_case,
        test_run_id=run_id,
    )

    db.add(artifact)
    await db.flush()
    await db.refresh(artifact)

    return artifact


@router.get("/{artifact_id}")
async def download_artifact(
    artifact_id: int,
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """
    Download an artifact by ID.
    """
    result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    artifact = result.scalar_one_or_none()

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # C3: Reconstruct the full path from the trusted upload root + relative filename
    upload_root = get_upload_root()
    storage_path = (upload_root / artifact.storage_path).resolve()

    # Double-check the resolved path is inside the upload root (defense-in-depth)
    if not str(storage_path).startswith(str(upload_root)):
        raise HTTPException(status_code=400, detail="Invalid artifact path.")

    if not storage_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(storage_path),
        filename=artifact.original_filename,
        media_type=artifact.content_type,
    )


@router.get("/info/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact_info(
    artifact_id: int,
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """
    Get artifact metadata without downloading.
    """
    result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    artifact = result.scalar_one_or_none()

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return artifact


@router.delete("/{artifact_id}", status_code=204)
async def delete_artifact(
    artifact_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Delete an artifact.
    """
    result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    artifact = result.scalar_one_or_none()

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # C3: Resolve path safely before deletion
    upload_root = get_upload_root()
    storage_path = (upload_root / artifact.storage_path).resolve()

    if str(storage_path).startswith(str(upload_root)) and storage_path.exists():
        os.remove(storage_path)

    await db.delete(artifact)
