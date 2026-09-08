"""Minting and resolution for Test Station enrolment keys."""

import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RunnerApiKey

# Recognisable in a shell history or a CI log.
KEY_PREFIX = "budrnr_"
PREFIX_LENGTH = 12


def generate_key() -> str:
    """Return a new plaintext enrolment key. Never persisted in this form."""
    return f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def key_prefix(plaintext: str) -> str:
    """The leading characters kept for display."""
    return plaintext[:PREFIX_LENGTH]


def mint_key(label: str, created_by_user_id: Optional[int]) -> Tuple[RunnerApiKey, str]:
    """Build an unsaved key row and return it with the plaintext to show once."""
    plaintext = generate_key()
    record = RunnerApiKey(
        label=label,
        key_hash=hash_key(plaintext),
        key_prefix=key_prefix(plaintext),
        created_by_user_id=created_by_user_id,
    )
    return record, plaintext


async def resolve_key(presented: str, db: AsyncSession) -> Optional[RunnerApiKey]:
    """Find the key row a presented secret belongs to, or None."""
    if not presented:
        return None
    digest = hash_key(presented)
    result = await db.execute(select(RunnerApiKey).where(RunnerApiKey.key_hash == digest))
    record = result.scalar_one_or_none()
    if record is None:
        return None
    if not hmac.compare_digest(record.key_hash, digest):
        return None
    return record


def mark_used(record: RunnerApiKey) -> None:
    record.last_used_at = datetime.utcnow()
