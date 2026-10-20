"""Atomic browser approval and PKCE exchange for user-scoped CLI sessions.

A rejected request raises TokenValidationError whose detail is one of the rejection codes
below; the routes record that code in the audit log and answer with a generic message.
"""

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.models.cli_auth_session import CliAuthSession
from app.models.user import User
from app.models.user_token import UserTokenPurpose
from app.schemas.cli_auth import CliStartRequest
from app.services.token_service import (
    TokenValidationError,
    claim_token,
    create_user_token,
    find_token,
    hash_token,
)

INVALID_AUTHORIZATION = "Invalid or expired authorization session"
SESSION_LIFETIME = timedelta(minutes=10)

NOT_PENDING = "not_pending"
NOT_APPROVED = "unknown_or_unapproved_session"
CODE_OR_VERIFIER_MISMATCH = "code_or_verifier_mismatch"
INACTIVE_OR_CHANGED_USER = "inactive_or_changed_user"
EXPIRED_OR_CONSUMED = "expired_or_consumed"
INVALID_REFRESH_TOKEN = "invalid_token"
INACTIVE_OR_MISSING_USER = "inactive_or_missing_user"


def utcnow() -> datetime:
    """Return the naive UTC timestamp used by stored authentication records."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def purge_finished_sessions(db: AsyncSession, now: datetime) -> None:
    """Delete the authorization sessions that have expired or been exchanged."""
    await db.execute(
        delete(CliAuthSession).where(
            or_(CliAuthSession.expires_at <= now, CliAuthSession.consumed_at.is_not(None))
        )
    )


async def start_session(db: AsyncSession, data: CliStartRequest) -> CliAuthSession:
    """Delete finished sessions, then create a pending authorization with a ten-minute lifetime."""
    now = utcnow()
    await purge_finished_sessions(db, now)
    session = CliAuthSession(**data.model_dump(), expires_at=now + SESSION_LIFETIME)
    db.add(session)
    await db.flush()
    return session


async def pending_session(db: AsyncSession, session_id: UUID) -> CliAuthSession:
    """Return an unapproved, unconsumed request that has not expired."""
    result = await db.execute(
        select(CliAuthSession).where(
            CliAuthSession.id == session_id,
            CliAuthSession.expires_at > utcnow(),
            CliAuthSession.consumed_at.is_(None),
            CliAuthSession.exchange_code_hash.is_(None),
            CliAuthSession.user_id.is_(None),
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise TokenValidationError(NOT_PENDING)
    return session


async def approve_session(
    db: AsyncSession, session_id: UUID, user: User
) -> tuple[CliAuthSession, str]:
    """Bind a pending request to the active user's current session version once."""
    version = user.session_version
    current = await db.get(
        User, user.id, populate_existing=True, with_for_update={"key_share": True}
    )
    if current is None or not current.is_active or current.session_version != version:
        raise TokenValidationError(INACTIVE_OR_CHANGED_USER)
    code = secrets.token_urlsafe(32)
    result = await db.execute(
        update(CliAuthSession)
        .where(
            CliAuthSession.id == session_id,
            CliAuthSession.expires_at > utcnow(),
            CliAuthSession.consumed_at.is_(None),
            CliAuthSession.exchange_code_hash.is_(None),
            CliAuthSession.user_id.is_(None),
        )
        .values(
            exchange_code_hash=hash_token(code),
            user_id=current.id,
            approved_session_version=current.session_version,
        )
        .returning(CliAuthSession)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise TokenValidationError(NOT_PENDING)
    return session, code


def callback_target(session: CliAuthSession, code: str) -> str:
    """Append the approved code and original state to the validated loopback URI."""
    target = urlsplit(session.redirect_uri)
    query = parse_qsl(target.query, keep_blank_values=True) + [
        ("code", code),
        ("state", session.state),
    ]
    return urlunsplit(target._replace(query=urlencode(query)))


async def issue_credentials(db: AsyncSession, user: User) -> tuple[str, str]:
    """Create a rotating refresh token and an access JWT bound to its live row."""
    refresh_token = await create_user_token(
        db,
        user_id=user.id,
        purpose=UserTokenPurpose.refresh,
        ttl_hours=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24,
        invalidate_existing=False,
    )
    row = await find_token(db, token=refresh_token, purpose=UserTokenPurpose.refresh)
    access_token = create_access_token(
        {"sub": str(user.id), "type": "user", "ver": user.session_version, "cli_refresh_id": row.id}
    )
    return access_token, refresh_token


async def exchange_session(
    db: AsyncSession, *, session_id: UUID, code: str, code_verifier: str
) -> tuple[User, str, str]:
    """Consume an approved request once after checking the code, proof key and account."""
    session = await db.get(CliAuthSession, session_id)
    if session is None or session.user_id is None or session.exchange_code_hash is None:
        raise TokenValidationError(NOT_APPROVED)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest())
        .decode("ascii")
        .rstrip("=")
    )
    if not hmac.compare_digest(
        hash_token(code), session.exchange_code_hash
    ) or not hmac.compare_digest(challenge, session.code_challenge):
        raise TokenValidationError(CODE_OR_VERIFIER_MISMATCH)
    user = await db.get(
        User, session.user_id, populate_existing=True, with_for_update={"key_share": True}
    )
    if (
        user is None
        or not user.is_active
        or user.session_version != session.approved_session_version
    ):
        raise TokenValidationError(INACTIVE_OR_CHANGED_USER)
    now = utcnow()
    result = await db.execute(
        update(CliAuthSession)
        .where(
            CliAuthSession.id == session_id,
            CliAuthSession.user_id == user.id,
            CliAuthSession.approved_session_version == user.session_version,
            CliAuthSession.exchange_code_hash == hash_token(code),
            CliAuthSession.expires_at > now,
            CliAuthSession.consumed_at.is_(None),
        )
        .values(consumed_at=now)
        .returning(CliAuthSession.id)
    )
    if result.scalar_one_or_none() is None:
        raise TokenValidationError(EXPIRED_OR_CONSUMED)
    access_token, refresh_token = await issue_credentials(db, user)
    return user, access_token, refresh_token


async def refresh_credentials(db: AsyncSession, token: str) -> tuple[User, str, str]:
    """Consume a refresh token through claim_token and issue replacement credentials.

    Every unused, unexpired token of purpose refresh is accepted, the same pool the browser
    refresh cookie and invalidate_all_refresh_tokens use.
    """
    row = await find_token(db, token=token, purpose=UserTokenPurpose.refresh)
    if row is None:
        raise TokenValidationError(INVALID_REFRESH_TOKEN)
    user = await db.get(
        User, row.user_id, populate_existing=True, with_for_update={"key_share": True}
    )
    if user is None or not user.is_active:
        raise TokenValidationError(INACTIVE_OR_MISSING_USER)
    try:
        await claim_token(db, token=token, purpose=UserTokenPurpose.refresh)
    except TokenValidationError as exc:
        raise TokenValidationError(INVALID_REFRESH_TOKEN) from exc
    access_token, refresh_token = await issue_credentials(db, user)
    return user, access_token, refresh_token
