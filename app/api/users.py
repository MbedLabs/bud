"""
Users API endpoints (admin only): CRUD for user management.
"""

import logging
import secrets
import string
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_role
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.user_token import UserToken, UserTokenPurpose
from app.schemas.auth import (
    AdminEmailChangeRequest,
    InviteCreateRequest,
    InviteResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.mail_service import (
    MailConfigurationError,
    send_email_change_email,
    send_invite_email,
)
from app.services.token_service import create_user_token, invalidate_tokens

logger = logging.getLogger(__name__)

router = APIRouter()

require_admin = require_role(UserRole.admin)


async def _get_user_or_404(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id, populate_existing=True, with_for_update=True)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _validate_new_email(db: AsyncSession, user: User, new_email: str) -> None:
    if new_email == user.email:
        raise HTTPException(status_code=400, detail="New email matches the current email")
    existing = await db.execute(select(User).where(User.email == new_email, User.id != user.id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already in use")


async def _send_email_change_confirmation(
    db: AsyncSession,
    *,
    user: User,
    new_email: str,
    admin: User,
) -> UserResponse:
    await _validate_new_email(db, user, new_email)
    await invalidate_tokens(db, user.id, purpose=UserTokenPurpose.email_change)

    user.pending_email = new_email
    user.email_change_status = "awaiting_confirmation"
    user.email_change_requested_at = user.email_change_requested_at or datetime.utcnow()
    token = await create_user_token(
        db,
        user_id=user.id,
        purpose=UserTokenPurpose.email_change,
        ttl_hours=settings.EMAIL_VERIFICATION_TOKEN_TTL_HOURS,
        created_by_user_id=admin.id,
        target_email=new_email,
    )
    confirm_link = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/confirm-email-change#token={token}"
    try:
        send_email_change_email(
            to_email=new_email,
            full_name=user.full_name,
            old_email=user.email,
            new_email=new_email,
            confirm_link=confirm_link,
        )
    except MailConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


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
    invite_link = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/accept-invite#token={invite_token}"

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
    invite_link = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/accept-invite#token={invite_token}"

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


@router.post("/{user_id}/email", response_model=UserResponse)
async def start_email_change(
    user_id: int,
    data: AdminEmailChangeRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Let an administrator propose a new login email.

    The address is not applied directly. A confirmation link is sent to the new
    mailbox and the login changes only after that link is used.
    """
    user = await _get_user_or_404(db, user_id)
    user.email_change_requested_at = datetime.utcnow()
    return await _send_email_change_confirmation(
        db, user=user, new_email=str(data.new_email), admin=admin
    )


@router.post("/{user_id}/email/approve", response_model=UserResponse)
async def approve_email_change(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user_or_404(db, user_id)
    if not user.pending_email or user.email_change_status != "requested":
        raise HTTPException(
            status_code=400,
            detail="No email change request is waiting for administrator approval",
        )
    return await _send_email_change_confirmation(
        db, user=user, new_email=user.pending_email, admin=admin
    )


@router.delete("/{user_id}/email", response_model=UserResponse)
async def reject_email_change(
    user_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user_or_404(db, user_id)
    if not user.pending_email:
        raise HTTPException(status_code=400, detail="No pending email change")
    user.pending_email = None
    user.email_change_status = None
    user.email_change_requested_at = None
    await invalidate_tokens(db, user.id, purpose=UserTokenPurpose.email_change)
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


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

    try:
        # Delete tokens for this user
        await db.execute(delete(UserToken).where(UserToken.user_id == user_id))
        # Nullify creator of tokens
        await db.execute(
            update(UserToken)
            .where(UserToken.created_by_user_id == user_id)
            .values(created_by_user_id=None)
        )
        # Nullify invited_by references
        await db.execute(
            update(User).where(User.invited_by_user_id == user_id).values(invited_by_user_id=None)
        )

        await db.delete(user)
        await db.flush()
    except IntegrityError as exc:
        logger.error(f"Integrity error deleting user {user_id}: {exc}")
        raise HTTPException(
            status_code=409,
            detail="User could not be deleted because related records still reference this account",
        ) from exc
    except Exception as exc:
        logger.error(f"Unexpected error deleting user {user_id}: {exc}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while deleting the user",
        ) from exc
