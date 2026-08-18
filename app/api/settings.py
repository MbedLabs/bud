"""
Settings API endpoints.
"""

from datetime import datetime
from typing import List
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_role
from app.db import get_db
from app.models import SystemSetting, UserRole
from app.models.user import User
from app.schemas import (
    ALMIntegrationSettings,
    ALMIntegrationSettingsUpdate,
    SystemSettingResponse,
    SystemSettingUpdate,
)
from app.services.integration_secrets import encrypt_integration_secret

router = APIRouter()
PROTECTED_SETTING_KEYS = {
    "bloom_token",
    "bloom_token_encrypted",
    "bloom_token_prefix",
}


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlparse(url)
    default_port = 443 if parsed.scheme.lower() == "https" else 80
    try:
        port = parsed.port
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bloom URL has an invalid port.") from exc
    return parsed.scheme.lower(), (parsed.hostname or "").lower(), port or default_port


@router.get("", response_model=List[SystemSettingResponse])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """
    Get all system settings. Restricted to admins.
    """
    result = await db.execute(
        select(SystemSetting)
        .where(SystemSetting.key.notin_(PROTECTED_SETTING_KEYS))
        .order_by(SystemSetting.key)
    )
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
    if key in PROTECTED_SETTING_KEYS:
        raise HTTPException(status_code=404, detail="Setting not found")
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
    if key in PROTECTED_SETTING_KEYS:
        raise HTTPException(
            status_code=403,
            detail="Integration secrets must use the dedicated integration endpoint.",
        )
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
    token_setting = await db.get(SystemSetting, "bloom_token_encrypted")
    prefix_setting = await db.get(SystemSetting, "bloom_token_prefix")
    rotated_setting = await db.get(SystemSetting, "bloom_token_rotated_at")

    return ALMIntegrationSettings(
        bloom_url=url_setting.value if url_setting else "",
        has_bloom_token=bool(token_setting and token_setting.value),
        bloom_token_prefix=prefix_setting.value if prefix_setting else None,
        bloom_token_rotated_at=(
            datetime.fromisoformat(rotated_setting.value) if rotated_setting else None
        ),
    )


@router.post("/integrations/PLM", response_model=ALMIntegrationSettings)
async def update_alm_integration(
    data: ALMIntegrationSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """
    Update PLM integration settings.
    """
    parsed = urlparse(data.bloom_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise HTTPException(status_code=422, detail="Bloom URL must be an absolute HTTP(S) URL.")
    new_origin = _origin(data.bloom_url)

    updates = [("bloom_url", data.bloom_url.rstrip("/"))]
    masked = data.bloom_token is not None and set(data.bloom_token) == {"*"}
    current_url = await db.get(SystemSetting, "bloom_url")
    current_token = await db.get(SystemSetting, "bloom_token_encrypted")
    origin_changed = bool(
        current_url and current_url.value and _origin(current_url.value) != new_origin
    )
    supplies_new_token = bool(data.bloom_token and not masked)
    if (
        origin_changed
        and current_token
        and current_token.value
        and not supplies_new_token
        and not data.clear_bloom_token
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Changing the Bloom destination requires re-entering a Bloom "
                "result-sync credential or clearing the saved credential."
            ),
        )
    if data.clear_bloom_token:
        for key in (
            "bloom_token_encrypted",
            "bloom_token_prefix",
            "bloom_token_rotated_at",
            "bloom_token",
        ):
            setting = await db.get(SystemSetting, key)
            if setting:
                await db.delete(setting)
    elif data.bloom_token and not masked:
        if not data.bloom_token.startswith("blm_sync_"):
            raise HTTPException(
                status_code=422,
                detail="Bloom token must be a scoped blm_sync_ service credential.",
            )
        rotated_at = datetime.utcnow()
        updates.extend(
            [
                ("bloom_token_encrypted", encrypt_integration_secret(data.bloom_token)),
                ("bloom_token_prefix", data.bloom_token[:20]),
                ("bloom_token_rotated_at", rotated_at.isoformat()),
            ]
        )

    for key, val in updates:
        setting = await db.get(SystemSetting, key)
        if setting:
            setting.value = val
        else:
            db.add(SystemSetting(key=key, value=val))

    legacy = await db.get(SystemSetting, "bloom_token")
    if legacy:
        await db.delete(legacy)
    await db.commit()
    return await get_alm_integration(db=db, _admin=_admin)
