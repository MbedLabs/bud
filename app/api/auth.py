"""
Auth API endpoints: login, get current user, update profile.
Also provides shared auth dependencies used across the app.
"""

import logging
from datetime import datetime
from typing import Optional, Union

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import limiter
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    oauth2_scheme,
    verify_password,
)
from app.db.database import get_db
from app.models import Runner
from app.models.user import User, UserRole
from app.models.user_token import UserTokenPurpose
from app.schemas.auth import (
    AcceptInviteRequest,
    AcceptInviteResponse,
    ConfirmEmailChangeRequest,
    EmailChangeRequest,
    ForgotPasswordRequest,
    GenericMessageResponse,
    InviteInfoRequest,
    InviteInfoResponse,
    LoginRequest,
    PasswordChange,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    UserUpdate,
    VerifyEmailRequest,
)
from app.services.mail_service import (
    MailConfigurationError,
    send_password_reset_email,
    send_verification_email,
)
from app.services.token_service import (
    TokenValidationError,
    claim_token,
    create_user_token,
    find_token,
    get_valid_token,
    invalidate_all_refresh_tokens,
    invalidate_tokens,
    mark_token_used,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Refresh token is delivered as an httpOnly cookie scoped to the auth endpoints,
# rotated on every use, and revocable via the user_tokens table.
REFRESH_COOKIE_NAME = "bud_refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=bool(settings.AUTH_COOKIE_SECURE),
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=bool(settings.AUTH_COOKIE_SECURE),
        samesite="strict",
    )


async def _issue_refresh_cookie(db: AsyncSession, response: Response, user_id: int) -> None:
    raw_token = await create_user_token(
        db,
        user_id=user_id,
        purpose=UserTokenPurpose.refresh,
        ttl_hours=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24,
        invalidate_existing=False,  # allow concurrent sessions (multiple devices/tabs)
    )
    _set_refresh_cookie(response, raw_token)


async def get_current_active_entity(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Union[User, Runner]:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    sub = payload.get("sub")
    entity_type = payload.get("type")

    if sub is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if entity_type == "runner":
        result = await db.execute(select(Runner).where(Runner.account == sub))
        entity = result.scalar_one_or_none()
    elif entity_type == "user":
        try:
            entity_id = int(sub)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID")
        result = await db.execute(select(User).where(User.id == entity_id))
        entity = result.scalar_one_or_none()
        # Reject tokens minted before a password/reset/email-change bumped the
        # user's session_version. Missing "ver" (a token predating this feature)
        # never matches, so those tokens are also retired on first use.
        if entity is not None and payload.get("ver") != entity.session_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired, please log in again",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if entity is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Entity not found")

    # Both models have is_active
    if not entity.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    return entity


async def get_current_user(
    current_entity: Union[User, Runner] = Depends(get_current_active_entity),
) -> User:
    if not isinstance(current_entity, User):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User privileges required.",
        )
    return current_entity


def require_role(*roles: UserRole):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return current_user

    return role_checker


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated"
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "type": "user", "ver": user.session_version}
    )
    await _issue_refresh_cookie(db, response, user.id)

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
):
    """Exchange a valid refresh cookie for a new access token, rotating the
    refresh token (single-use). If a stolen token is replayed after the real
    client has rotated, it is already marked used and is rejected."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session",
    )
    if not refresh_token:
        raise unauthorized
    # Atomically consume the presented token. Two requests racing on the same
    # cookie can only produce one winner here, so only one replacement is issued.
    try:
        claimed = await claim_token(db, token=refresh_token, purpose=UserTokenPurpose.refresh)
    except TokenValidationError:
        _clear_refresh_cookie(response)
        raise unauthorized

    user = await db.get(User, claimed.user_id)
    if user is None or not user.is_active:
        _clear_refresh_cookie(response)
        raise unauthorized

    # Consumed above; issue the replacement in the same transaction.
    await _issue_refresh_cookie(db, response, user.id)
    access_token = create_access_token(
        data={"sub": str(user.id), "type": "user", "ver": user.session_version}
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", response_model=GenericMessageResponse)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
):
    """Revoke the current refresh token server-side and clear the cookie."""
    if refresh_token:
        token_row = await find_token(db, token=refresh_token, purpose=UserTokenPurpose.refresh)
        if token_row is not None and token_row.used_at is None:
            await mark_token_used(db, token_row)
    _clear_refresh_cookie(response)
    return GenericMessageResponse(message="Logged out")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.full_name is not None:
        current_user.full_name = data.full_name
    # Email changes are not applied here: they require the current password and a
    # confirmation of the new address via POST /me/email. Any email in this
    # payload is ignored so an unconfirmed address can never become the login.

    await db.flush()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.post("/me/email", response_model=GenericMessageResponse)
async def request_email_change(
    data: EmailChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Request an administrator-controlled email change.

    The current password proves that the request came from the account holder.
    No token or email is issued until an administrator approves the request.
    """
    current_user = await db.get(
        User,
        current_user.id,
        populate_existing=True,
        with_for_update=True,
    )
    if current_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_email = data.new_email
    if new_email == current_user.email:
        raise HTTPException(status_code=400, detail="New email matches the current email")

    existing = await db.execute(
        select(User).where(User.email == new_email, User.id != current_user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already in use")

    await invalidate_tokens(db, current_user.id, purpose=UserTokenPurpose.email_change)
    current_user.pending_email = new_email
    current_user.email_change_status = "requested"
    current_user.email_change_requested_at = datetime.utcnow()
    await db.flush()
    return GenericMessageResponse(
        message="Email change requested. An administrator must approve it before a confirmation email is sent."
    )


@router.delete("/me/email", response_model=GenericMessageResponse)
async def cancel_email_change(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending email change: clear the pending address and burn any
    outstanding confirmation tokens."""
    current_user = await db.get(
        User,
        current_user.id,
        populate_existing=True,
        with_for_update=True,
    )
    if current_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    current_user.pending_email = None
    current_user.email_change_status = None
    current_user.email_change_requested_at = None
    await invalidate_tokens(db, current_user.id, purpose=UserTokenPurpose.email_change)
    await db.flush()
    return GenericMessageResponse(message="Pending email change cancelled")


@router.post("/confirm-email-change", response_model=GenericMessageResponse)
async def confirm_email_change(
    data: ConfirmEmailChangeRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Confirm a verified email change with the one-time token sent to the new
    address. Switches the login email, marks it verified, and ends every existing
    session so a fresh login with the new address is required."""
    try:
        candidate = await get_valid_token(
            db,
            token=data.token,
            purpose=UserTokenPurpose.email_change,
        )
    except TokenValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc

    user = await db.get(
        User,
        candidate.user_id,
        populate_existing=True,
        with_for_update=True,
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.pending_email or user.email_change_status != "awaiting_confirmation":
        raise HTTPException(status_code=400, detail="No pending email change")
    if not candidate.target_email or user.pending_email != candidate.target_email:
        raise HTTPException(
            status_code=400,
            detail="Email change token no longer matches the pending address",
        )

    try:
        claimed = await claim_token(db, token=data.token, purpose=UserTokenPurpose.email_change)
    except TokenValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    if claimed.target_email != candidate.target_email:
        raise HTTPException(status_code=400, detail="Invalid token")

    # Guard against the address being taken between request and confirmation.
    existing = await db.execute(
        select(User).where(User.email == candidate.target_email, User.id != user.id)
    )
    if existing.scalar_one_or_none():
        user.pending_email = None
        user.email_change_status = None
        user.email_change_requested_at = None
        await db.flush()
        raise HTTPException(status_code=400, detail="Email already in use")

    user.email = candidate.target_email
    user.pending_email = None
    user.email_change_status = None
    user.email_change_requested_at = None
    user.email_verified_at = datetime.utcnow()
    # Confirmed identity change ends every existing session.
    user.session_version += 1
    await invalidate_all_refresh_tokens(db, user.id)
    _clear_refresh_cookie(response)
    await db.flush()
    return GenericMessageResponse(message="Email address updated. Please log in again.")


@router.put("/me/password", response_model=UserResponse)
async def change_password(
    data: PasswordChange,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = get_password_hash(data.new_password)
    current_user.password_set_at = datetime.utcnow()
    # End every existing session: retire outstanding access tokens (version bump)
    # and refresh tokens, and drop this device's refresh cookie. A fresh login is
    # required afterward.
    current_user.session_version += 1
    await invalidate_all_refresh_tokens(db, current_user.id)
    _clear_refresh_cookie(response)
    await db.flush()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.post("/invite-info", response_model=InviteInfoResponse)
async def get_invite_info(data: InviteInfoRequest, db: AsyncSession = Depends(get_db)):
    user_token = await find_token(db, token=data.token, purpose=UserTokenPurpose.invite)
    if user_token is None:
        raise HTTPException(status_code=400, detail="Invalid token")

    user = await db.get(User, user_token.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    expired = user_token.expires_at < datetime.utcnow()
    used = user_token.used_at is not None
    return InviteInfoResponse(
        email=user.email,
        full_name=user.full_name,
        valid=not expired and not used,
        expired=expired,
    )


@router.post("/accept-invite", response_model=AcceptInviteResponse)
async def accept_invite(data: AcceptInviteRequest, db: AsyncSession = Depends(get_db)):
    try:
        claimed = await claim_token(db, token=data.token, purpose=UserTokenPurpose.invite)
    except TokenValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc

    user = await db.get(User, claimed.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.invite_accepted_at is not None:
        raise HTTPException(status_code=400, detail="Invite already accepted")

    user.hashed_password = get_password_hash(data.password)
    now = datetime.utcnow()
    user.invite_accepted_at = now
    user.password_set_at = now
    # Accepting an invitation proves control of the invited address, so treat it
    # as verification. No separate verification email is sent (which also means
    # this flow no longer depends on SMTP being configured).
    user.email_verified_at = now

    await db.flush()
    return AcceptInviteResponse(
        requires_email_verification=False,
        email=user.email,
        message="Invitation accepted.",
    )


@router.post("/verify-email", response_model=GenericMessageResponse)
async def verify_email(data: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    try:
        claimed = await claim_token(
            db,
            token=data.token,
            purpose=UserTokenPurpose.email_verification,
        )
    except TokenValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc

    user = await db.get(User, claimed.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.email_verified_at is not None:
        raise HTTPException(status_code=400, detail="Email already verified")

    user.email_verified_at = datetime.utcnow()
    await db.flush()
    return GenericMessageResponse(message="Email verified successfully")


@router.post("/resend-verification", response_model=GenericMessageResponse)
@limiter.limit("5/hour")
async def resend_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.email_verified_at is not None:
        raise HTTPException(status_code=400, detail="Email already verified")

    verification_token = await create_user_token(
        db,
        user_id=current_user.id,
        purpose=UserTokenPurpose.email_verification,
        ttl_hours=settings.EMAIL_VERIFICATION_TOKEN_TTL_HOURS,
    )
    verification_link = (
        f"{settings.FRONTEND_BASE_URL.rstrip('/')}/verify-email#token={verification_token}"
    )

    try:
        send_verification_email(
            to_email=current_user.email,
            full_name=current_user.full_name,
            verification_link=verification_link,
        )
    except MailConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await db.flush()
    return GenericMessageResponse(message="Verification email sent")


@router.post("/forgot-password", response_model=GenericMessageResponse)
@limiter.limit("5/hour")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    response = GenericMessageResponse(
        message="If the account exists, a password reset email has been sent"
    )

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return response

    reset_token = await create_user_token(
        db,
        user_id=user.id,
        purpose=UserTokenPurpose.password_reset,
        ttl_hours=settings.PASSWORD_RESET_TOKEN_TTL_HOURS,
    )
    reset_link = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/reset-password#token={reset_token}"

    try:
        send_password_reset_email(
            to_email=user.email,
            full_name=user.full_name,
            reset_link=reset_link,
        )
    except MailConfigurationError:
        logger.exception("Password reset email could not be sent for user_id=%s", user.id)

    await db.flush()
    return response


@router.post("/reset-password", response_model=GenericMessageResponse)
async def reset_password(
    data: ResetPasswordRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        claimed = await claim_token(
            db,
            token=data.token,
            purpose=UserTokenPurpose.password_reset,
        )
    except TokenValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc

    user = await db.get(User, claimed.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = get_password_hash(data.new_password)
    user.password_set_at = datetime.utcnow()
    # End every existing session, exactly as on password change.
    user.session_version += 1
    await invalidate_all_refresh_tokens(db, user.id)
    _clear_refresh_cookie(response)
    await db.flush()
    return GenericMessageResponse(message="Password reset successfully")
