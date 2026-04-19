import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_token import UserToken, UserTokenPurpose


class TokenValidationError(Exception):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


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
            .values(used_at=datetime.utcnow())
        )

    raw_token = generate_raw_token()
    db.add(
        UserToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=hash_token(raw_token),
            expires_at=datetime.utcnow() + timedelta(hours=ttl_hours),
            created_by_user_id=created_by_user_id,
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
        raise TokenValidationError("Invalid token")
    if result.used_at is not None:
        raise TokenValidationError("Token has already been used")
    if result.expires_at < datetime.utcnow():
        raise TokenValidationError("Token has expired")
    return result


async def mark_token_used(db: AsyncSession, user_token: UserToken) -> None:
    user_token.used_at = datetime.utcnow()
    await db.flush()
