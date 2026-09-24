"""
Settings API endpoints.
"""

from datetime import datetime
from typing import List
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import wait_fixed

from app.api.auth import require_role
from app.db import get_db
from app.models import NotificationChannel, SystemSetting, UserRole
from app.models.user import User
from app.schemas import (
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    NotificationTestResult,
    PLMIntegrationSettings,
    PLMIntegrationSettingsUpdate,
    SystemSettingResponse,
    SystemSettingUpdate,
)
from app.services.integration_secrets import encrypt_integration_secret
from app.services.notify import send_test_message

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
    db: AsyncSession = Depends(get_db, scope="function"),
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
    db: AsyncSession = Depends(get_db, scope="function"),
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
    db: AsyncSession = Depends(get_db, scope="function"),
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


@router.get("/integrations/PLM", response_model=PLMIntegrationSettings)
async def get_plm_integration(
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """
    Get PLM integration settings (Bloom).
    """
    url_setting = await db.get(SystemSetting, "bloom_url")
    token_setting = await db.get(SystemSetting, "bloom_token_encrypted")
    prefix_setting = await db.get(SystemSetting, "bloom_token_prefix")
    rotated_setting = await db.get(SystemSetting, "bloom_token_rotated_at")

    return PLMIntegrationSettings(
        bloom_url=url_setting.value if url_setting else "",
        has_bloom_token=bool(token_setting and token_setting.value),
        bloom_token_prefix=prefix_setting.value if prefix_setting else None,
        bloom_token_rotated_at=(
            datetime.fromisoformat(rotated_setting.value) if rotated_setting else None
        ),
    )


@router.post("/integrations/PLM", response_model=PLMIntegrationSettings)
async def update_plm_integration(
    data: PLMIntegrationSettingsUpdate,
    db: AsyncSession = Depends(get_db, scope="function"),
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
    return await get_plm_integration(db=db, _admin=_admin)


def _webhook_url(url: str) -> str:
    """An absolute HTTP(S) URL without embedded credentials, or a 422."""
    parsed = urlparse(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise HTTPException(status_code=422, detail="Webhook URL must be an absolute HTTP(S) URL.")
    return url


def _url_prefix(url: str) -> str:
    """The part of a webhook URL that is safe to show again."""
    return url[:40] + ("..." if len(url) > 40 else "")


def _channel_response(channel: NotificationChannel) -> NotificationChannelResponse:
    """Serialise a channel without its URL or secret."""
    return NotificationChannelResponse(
        id=channel.id,
        name=channel.name,
        format=channel.format,
        url_prefix=channel.url_prefix,
        run_filter=channel.run_filter,
        enabled=channel.enabled,
        has_secret=bool(channel.secret_encrypted),
        created_at=channel.created_at,
    )


async def _get_channel_or_404(db: AsyncSession, channel_id: int) -> NotificationChannel:
    """Load a channel or answer 404."""
    channel = await db.get(NotificationChannel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Notification channel not found")
    return channel


async def _name_taken(db: AsyncSession, name: str, exclude_id: int | None = None) -> bool:
    """Whether another channel already uses this name."""
    query = select(NotificationChannel.id).where(NotificationChannel.name == name)
    if exclude_id is not None:
        query = query.where(NotificationChannel.id != exclude_id)
    return (await db.execute(query)).scalar_one_or_none() is not None


@router.get("/notifications/channels", response_model=List[NotificationChannelResponse])
async def list_notification_channels(
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """List the channels finished runs are posted to."""
    channels = (
        (await db.execute(select(NotificationChannel).order_by(NotificationChannel.name)))
        .scalars()
        .all()
    )
    return [_channel_response(c) for c in channels]


@router.post("/notifications/channels", response_model=NotificationChannelResponse, status_code=201)
async def create_notification_channel(
    data: NotificationChannelCreate,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """Add a channel; its URL and secret are stored encrypted and never returned."""
    url = _webhook_url(data.url.strip())
    if await _name_taken(db, data.name):
        raise HTTPException(status_code=400, detail="A channel with this name already exists")
    channel = NotificationChannel(
        name=data.name,
        format=data.format,
        url_encrypted=encrypt_integration_secret(url),
        url_prefix=_url_prefix(url),
        secret_encrypted=encrypt_integration_secret(data.secret) if data.secret else None,
        run_filter=data.run_filter,
        enabled=data.enabled,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return _channel_response(channel)


@router.patch("/notifications/channels/{channel_id}", response_model=NotificationChannelResponse)
async def update_notification_channel(
    channel_id: int,
    data: NotificationChannelUpdate,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """Change a channel; a URL or secret is replaced only when given."""
    channel = await _get_channel_or_404(db, channel_id)
    if data.name is not None and data.name != channel.name:
        if await _name_taken(db, data.name, exclude_id=channel.id):
            raise HTTPException(status_code=400, detail="A channel with this name already exists")
        channel.name = data.name
    if data.format is not None:
        channel.format = data.format
    if data.url is not None:
        url = _webhook_url(data.url.strip())
        channel.url_encrypted = encrypt_integration_secret(url)
        channel.url_prefix = _url_prefix(url)
    if data.secret is not None:
        channel.secret_encrypted = encrypt_integration_secret(data.secret) if data.secret else None
    if data.run_filter is not None:
        channel.run_filter = data.run_filter
    if data.enabled is not None:
        channel.enabled = data.enabled
    await db.commit()
    await db.refresh(channel)
    return _channel_response(channel)


@router.delete("/notifications/channels/{channel_id}", status_code=204)
async def delete_notification_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """Remove a channel and its delivery history."""
    channel = await _get_channel_or_404(db, channel_id)
    await db.delete(channel)
    await db.commit()
    return Response(status_code=204)


@router.post("/notifications/channels/{channel_id}/test", response_model=NotificationTestResult)
async def test_notification_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """Post a sample run summary to the channel so the administrator sees it in the tool."""
    channel = await _get_channel_or_404(db, channel_id)
    delivery = await send_test_message(db, channel, wait=wait_fixed(1))
    await db.commit()
    return NotificationTestResult(
        delivered=bool(delivery and delivery.delivered),
        attempts=delivery.attempt if delivery else 0,
        status_code=delivery.status_code if delivery else None,
        error=delivery.error if delivery else None,
    )
