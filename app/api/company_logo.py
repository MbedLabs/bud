"""Company logo: an admin-uploaded customer logo shown on the report letterhead."""

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_active_entity, require_role
from app.db import get_db
from app.models import CompanyLogo, UserRole

router = APIRouter()

require_admin = require_role(UserRole.admin)
ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
MAX_LOGO_BYTES = 2_000_000


async def load_report_logo(db: AsyncSession) -> Optional[bytes]:
    """Return the stored company logo bytes, or None when none is set."""
    row = (await db.execute(select(CompanyLogo).limit(1))).scalar_one_or_none()
    return row.logo if row and row.logo else None


async def _company_logo_row(db: AsyncSession) -> CompanyLogo:
    row = (await db.execute(select(CompanyLogo).limit(1))).scalar_one_or_none()
    if row is None:
        row = CompanyLogo()
        db.add(row)
        await db.flush()
    return row


@router.put("/logo")
async def set_company_logo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin=Depends(require_admin),
):
    """Store the company logo used on report letterheads (admin only)."""
    if file.content_type not in ALLOWED_LOGO_TYPES:
        raise HTTPException(status_code=415, detail="Logo must be a PNG, JPEG, GIF or WebP image")
    raw = await file.read()
    if len(raw) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=413, detail="Logo image too large (max 2 MB)")
    logo = await _company_logo_row(db)
    logo.logo = raw
    logo.logo_content_type = file.content_type
    logo.logo_filename = file.filename
    await db.flush()
    return {"content_type": file.content_type, "size": len(raw)}


@router.get("/logo")
async def get_company_logo(
    db: AsyncSession = Depends(get_db, scope="function"),
    _entity=Depends(get_current_active_entity),
):
    """Return the stored company logo, or 404 when none is set."""
    row = (await db.execute(select(CompanyLogo).limit(1))).scalar_one_or_none()
    if row is None or not row.logo:
        raise HTTPException(status_code=404, detail="No company logo set")
    return Response(content=row.logo, media_type=row.logo_content_type or "image/png")


@router.delete("/logo", status_code=204)
async def delete_company_logo(
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin=Depends(require_admin),
):
    """Remove the stored company logo (admin only)."""
    row = (await db.execute(select(CompanyLogo).limit(1))).scalar_one_or_none()
    if row is not None:
        row.logo = None
        row.logo_content_type = None
        row.logo_filename = None
        await db.flush()
