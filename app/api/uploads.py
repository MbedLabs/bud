"""
File uploads API endpoints.
"""

import os
import uuid
import aiofiles
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.db import get_db
from app.models import Artifact
from app.schemas import ArtifactResponse
from app.core.config import settings

router = APIRouter()


async def ensure_upload_dir():
    """Ensure the upload directory exists."""
    upload_path = Path(settings.UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


@router.post("", response_model=ArtifactResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    test_case: Optional[str] = Form(None),
    run_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a file artifact (trace, log, etc.).
    
    Files are stored with a unique filename and can be associated with
    a test case and/or test run.
    """
    # Check file size
    file_size = 0
    content = await file.read()
    file_size = len(content)
    
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE} bytes",
        )
    
    # Generate unique filename
    ext = Path(file.filename).suffix if file.filename else ""
    unique_filename = f"{uuid.uuid4()}{ext}"
    
    # Save file
    upload_dir = await ensure_upload_dir()
    storage_path = upload_dir / unique_filename
    
    async with aiofiles.open(storage_path, "wb") as f:
        await f.write(content)
    
    # Create database record
    artifact = Artifact(
        filename=unique_filename,
        original_filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=file_size,
        storage_path=str(storage_path),
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
):
    """
    Download an artifact by ID.
    """
    result = await db.execute(
        select(Artifact).where(Artifact.id == artifact_id)
    )
    artifact = result.scalar_one_or_none()
    
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    if not os.path.exists(artifact.storage_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=artifact.storage_path,
        filename=artifact.original_filename,
        media_type=artifact.content_type,
    )


@router.get("/info/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact_info(
    artifact_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get artifact metadata without downloading.
    """
    result = await db.execute(
        select(Artifact).where(Artifact.id == artifact_id)
    )
    artifact = result.scalar_one_or_none()
    
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    return artifact


@router.delete("/{artifact_id}", status_code=204)
async def delete_artifact(
    artifact_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an artifact.
    """
    result = await db.execute(
        select(Artifact).where(Artifact.id == artifact_id)
    )
    artifact = result.scalar_one_or_none()
    
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    # Delete file from disk
    if os.path.exists(artifact.storage_path):
        os.remove(artifact.storage_path)
    
    # Delete database record
    await db.delete(artifact)
