"""
Users API endpoints (admin only): CRUD for user management.
"""

import secrets
import string
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_role
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.user_token import UserTokenPurpose
from app.schemas.auth import (
    InviteCreateRequest,
    InviteResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.mail_service import MailConfigurationError, send_invite_email
from app.services.token_service import create_user_token

router = APIRouter()

require_admin = require_role(UserRole.admin)


@router.get("", response_model=list[UserResponse])
async def list_users(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return [UserResponse.model_validate(u) for u in result.scalars().all()]


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
        role=data.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/invite", response_model=InviteResponse, status_code=201)
async def invite_user(
    data: InviteCreateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.email == data.email))
    user = existing.scalar_one_or_none()

    if user and user.password_set_at is not None:
        raise HTTPException(status_code=400, detail="Email already belongs to an active user")

    alphabet = string.ascii_letters + string.digits
    temp_password = "".join(secrets.choice(alphabet) for _ in range(12))

    if user is None:
        user = User(
            email=data.email,
            full_name=data.full_name,
            hashed_password=get_password_hash(temp_password),
            role=data.role,
            is_active=True,
            invited_at=datetime.utcnow(),
            invited_by_user_id=admin.id,
            last_invite_sent_at=datetime.utcnow(),
        )
        db.add(user)
        await db.flush()
    else:
        user.full_name = data.full_name
        user.role = data.role
        user.hashed_password = get_password_hash(temp_password)
        user.invited_at = user.invited_at or datetime.utcnow()
        user.invited_by_user_id = admin.id
        user.last_invite_sent_at = datetime.utcnow()

    invite_token = await create_user_token(
        db,
        user_id=user.id,
        purpose=UserTokenPurpose.invite,
        ttl_hours=settings.INVITE_TOKEN_TTL_HOURS,
        created_by_user_id=admin.id,
    )
    invite_link = (
        f"{settings.FRONTEND_BASE_URL.rstrip('/')}/accept-invite?token={invite_token}"
    )

    try:
        send_invite_email(
            to_email=user.email,
            full_name=user.full_name,
            invite_link=invite_link,
        )
    except MailConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await db.flush()
    await db.refresh(user)
    return InviteResponse(
        message="Invitation sent",
        user=UserResponse.model_validate(user),
        invite_link=invite_link,
    )


@router.post("/{user_id}/resend-invite", response_model=InviteResponse)
async def resend_invite(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.password_set_at is not None:
        raise HTTPException(status_code=400, detail="Invite already accepted")

    user.last_invite_sent_at = datetime.utcnow()
    alphabet = string.ascii_letters + string.digits
    temp_password = "".join(secrets.choice(alphabet) for _ in range(12))
    user.hashed_password = get_password_hash(temp_password)
    invite_token = await create_user_token(
        db,
        user_id=user.id,
        purpose=UserTokenPurpose.invite,
        ttl_hours=settings.INVITE_TOKEN_TTL_HOURS,
        created_by_user_id=admin.id,
    )
    invite_link = (
        f"{settings.FRONTEND_BASE_URL.rstrip('/')}/accept-invite?token={invite_token}"
    )

    try:
        send_invite_email(
            to_email=user.email,
            full_name=user.full_name,
            invite_link=invite_link,
        )
    except MailConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await db.flush()
    await db.refresh(user)
    return InviteResponse(
        message="Invitation resent",
        user=UserResponse.model_validate(user),
        invite_link=invite_link,
    )


@router.post("/{user_id}/revoke-invite", response_model=InviteResponse)
async def revoke_invite(
    user_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.password_set_at is not None:
        raise HTTPException(status_code=400, detail="Invite already accepted")

    user.is_active = False
    await db.flush()
    await db.refresh(user)
    return InviteResponse(message="Invitation revoked", user=UserResponse.model_validate(user))


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.email is not None:
        existing = await db.execute(
            select(User).where(User.email == data.email, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = data.email
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.role is not None:
        if user.role == UserRole.admin and data.role != UserRole.admin:
            raise HTTPException(status_code=400, detail="Admin role cannot be changed")
        if user.role != UserRole.admin and data.role == UserRole.admin:
            raise HTTPException(status_code=400, detail="Promoting users to admin is not allowed")
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active

    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if admin.id == user_id:
        raise HTTPException(
            status_code=400,
            detail="Admin users cannot delete their own account",
        )
    await db.delete(user)
