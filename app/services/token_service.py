import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_token import UserToken, UserTokenPurpose

INVALID_TOKEN = "Invalid token"


class TokenValidationError(Exception):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class ClaimedToken(NamedTuple):
    id: int
    user_id: int
    target_email: str | None


def generate_raw_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_user_token(
    db: AsyncSession,
    *,
    user_id: int,
    purpose: UserTokenPurpose,
    ttl_hours: int,
    created_by_user_id: int | None = None,
    target_email: str | None = None,
    invalidate_existing: bool = True,
) -> str:
    if invalidate_existing:
        await db.execute(
            update(UserToken)
            .where(
                UserToken.user_id == user_id,
                UserToken.purpose == purpose,
                UserToken.used_at.is_(None),
            )
            .values(used_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )

    raw_token = generate_raw_token()
    db.add(
        UserToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=ttl_hours),
            created_by_user_id=created_by_user_id,
            target_email=target_email,
        )
    )
    await db.flush()
    return raw_token


async def find_token(
    db: AsyncSession,
    *,
    token: str,
    purpose: UserTokenPurpose,
) -> UserToken | None:
    result = await db.execute(
        select(UserToken).where(
            UserToken.token_hash == hash_token(token),
            UserToken.purpose == purpose,
        )
    )
    return result.scalar_one_or_none()


async def get_valid_token(
    db: AsyncSession,
    *,
    token: str,
    purpose: UserTokenPurpose,
) -> UserToken:
    result = await find_token(db, token=token, purpose=purpose)
    if result is None:
        raise TokenValidationError(INVALID_TOKEN)
    if result.used_at is not None:
        raise TokenValidationError("Token has already been used")
    if result.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise TokenValidationError("Token has expired")
    return result


async def claim_token(
    db: AsyncSession,
    *,
    token: str,
    purpose: UserTokenPurpose,
) -> ClaimedToken:
    """Atomically consume a one-time token."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await db.execute(
        update(UserToken)
        .where(
            UserToken.token_hash == hash_token(token),
            UserToken.purpose == purpose,
            UserToken.used_at.is_(None),
            UserToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(UserToken.id, UserToken.user_id, UserToken.target_email)
    )
    row = result.first()
    if row is not None:
        return ClaimedToken(id=row[0], user_id=row[1], target_email=row[2])

    existing = await find_token(db, token=token, purpose=purpose)
    if existing is None:
        raise TokenValidationError(INVALID_TOKEN)
    if existing.used_at is not None:
        raise TokenValidationError("Token has already been used")
    if existing.expires_at < now:
        raise TokenValidationError("Token has expired")
    raise TokenValidationError(INVALID_TOKEN)


async def mark_token_used(db: AsyncSession, user_token: UserToken) -> None:
    user_token.used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()


async def invalidate_tokens(db: AsyncSession, user_id: int, *, purpose: UserTokenPurpose) -> None:
    """Revoke every unused token of a given purpose for a user."""
    await db.execute(
        update(UserToken)
        .where(
            UserToken.user_id == user_id,
            UserToken.purpose == purpose,
            UserToken.used_at.is_(None),
        )
        .values(used_at=datetime.now(timezone.utc).replace(tzinfo=None))
    )
    await db.flush()


async def invalidate_all_refresh_tokens(db: AsyncSession, user_id: int) -> None:
    """Revoke every unused refresh token for a user (all active sessions)."""
    await invalidate_tokens(db, user_id, purpose=UserTokenPurpose.refresh)


async def cancel_pending_email_change(db: AsyncSession, user) -> None:
    """Forget the user's pending email change and burn its confirmation tokens."""
    user.clear_pending_email_change()
    await invalidate_tokens(db, user.id, purpose=UserTokenPurpose.email_change)
    await db.flush()
