"""
Settings API endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_role
from app.db import get_db
from app.models import SystemSetting, UserRole
from app.models.user import User
from app.schemas import (ALMIntegrationSettings, SystemSettingResponse,
                         SystemSettingUpdate)

router = APIRouter()


@router.get("", response_model=List[SystemSettingResponse])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """
    Get all system settings. Restricted to admins.
    """
    result = await db.execute(select(SystemSetting).order_by(SystemSetting.key))
    return result.scalars().all()


@router.get("/{key}", response_model=SystemSettingResponse)
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """
    Get a specific system setting.
    """
    setting = await db.get(SystemSetting, key)
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    return setting


@router.put("/{key}", response_model=SystemSettingResponse)
async def update_setting(
    key: str,
    data: SystemSettingUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """
    Create or update a system setting.
    """
    setting = await db.get(SystemSetting, key)
    if setting:
        setting.value = data.value
        if data.description is not None:
            setting.description = data.description
    else:
        setting = SystemSetting(key=key, value=data.value, description=data.description)
        db.add(setting)

    await db.commit()
    await db.refresh(setting)
    return setting


@router.get("/integrations/PLM", response_model=ALMIntegrationSettings)
async def get_alm_integration(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """
    Get PLM integration settings (Bloom).
    """
    url_setting = await db.get(SystemSetting, "bloom_url")
    token_setting = await db.get(SystemSetting, "bloom_token")

    return ALMIntegrationSettings(
        bloom_url=url_setting.value if url_setting else "",
        bloom_token=token_setting.value if token_setting else "",
    )


@router.post("/integrations/PLM", response_model=ALMIntegrationSettings)
async def update_alm_integration(
    data: ALMIntegrationSettings,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """
    Update PLM integration settings.
    """
    for key, val in [("bloom_url", data.bloom_url), ("bloom_token", data.bloom_token)]:
        setting = await db.get(SystemSetting, key)
        if setting:
            setting.value = val
        else:
            db.add(SystemSetting(key=key, value=val))

    await db.commit()
    return data
