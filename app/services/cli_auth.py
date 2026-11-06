"""Atomic browser approval, denial and PKCE exchange for user-scoped CLI sessions.

A rejected request raises TokenValidationError whose detail is one of the rejection codes
below; the routes record that code in the audit log and answer with a generic message. A
code-mode request while code sign-in is turned off raises its subclass CodeModeDisabledError.
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
CODE_MODE_DISABLED = "code_mode_disabled"
CODE_MISMATCH = "request_code_mismatch"

CODE_MODE_OFF = "Code sign-in is turned off on this instance. Use callback mode."
REQUEST_CODE_BYTES = 5
REQUEST_CODE_LETTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")


class CodeModeDisabledError(TokenValidationError):
    """A code-mode request while the instance has code sign-in turned off."""

    def __init__(self) -> None:
        """Carry the code_mode_disabled rejection code."""
        super().__init__(CODE_MODE_DISABLED)


def utcnow() -> datetime:
    """Return the naive UTC timestamp used by stored authentication records."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def code_mode_refused(mode: str) -> bool:
    """Return whether the instance refuses a request in this mode."""
    return mode == "code" and not settings.CLI_CODE_MODE_ENABLED


async def ensure_mode_enabled(db: AsyncSession, session_id: UUID) -> None:
    """Raise CodeModeDisabledError for a stored code-mode request while code sign-in is off."""
    mode = await db.scalar(select(CliAuthSession.mode).where(CliAuthSession.id == session_id))
    if mode is not None and code_mode_refused(mode):
        raise CodeModeDisabledError()


def request_code(code_challenge: str) -> str:
    """Return the XXXX-XXXX base32 fingerprint of a PKCE challenge."""
    digest = hashlib.sha256(code_challenge.encode("ascii")).digest()[:REQUEST_CODE_BYTES]
    code = base64.b32encode(digest).decode("ascii")
    return f"{code[:4]}-{code[4:]}"


def typed_code_matches(typed: str, code_challenge: str) -> bool:
    """Return whether a typed request code, in any case and with spaces or hyphens, matches.

    A value that is not exactly eight characters from A-Z and 2-7 never matches.
    """
    letters = typed.upper().replace(" ", "").replace("-", "")
    expected = request_code(code_challenge).replace("-", "")
    if len(letters) != len(expected) or not set(letters) <= REQUEST_CODE_LETTERS:
        return False
    return hmac.compare_digest(letters, expected)


def pending_conditions(session_id: UUID) -> tuple:
    """Return the filters that select one unapproved, unconsumed, unexpired request."""
    return (
        CliAuthSession.id == session_id,
        CliAuthSession.expires_at > utcnow(),
        CliAuthSession.consumed_at.is_(None),
        CliAuthSession.exchange_code_hash.is_(None),
        CliAuthSession.user_id.is_(None),
    )


async def purge_finished_sessions(db: AsyncSession, now: datetime) -> None:
    """Delete the authorization sessions that have expired or been exchanged."""
    await db.execute(
        delete(CliAuthSession).where(
            or_(CliAuthSession.expires_at <= now, CliAuthSession.consumed_at.is_not(None))
        )
    )


async def start_session(db: AsyncSession, data: CliStartRequest) -> CliAuthSession:
    """Refuse a turned-off mode, delete finished sessions and create a ten-minute request."""
    if code_mode_refused(data.mode):
        raise CodeModeDisabledError()
    now = utcnow()
    await purge_finished_sessions(db, now)
    session = CliAuthSession(**data.model_dump(), expires_at=now + SESSION_LIFETIME)
    db.add(session)
    await db.flush()
    return session


async def pending_session(db: AsyncSession, session_id: UUID) -> CliAuthSession:
    """Return an unapproved, unconsumed, unexpired request whose mode the instance allows."""
    await ensure_mode_enabled(db, session_id)
    result = await db.execute(select(CliAuthSession).where(*pending_conditions(session_id)))
    session = result.scalar_one_or_none()
    if session is None:
        raise TokenValidationError(NOT_PENDING)
    return session


async def check_request_code(db: AsyncSession, session_id: UUID, typed: str) -> CliAuthSession:
    """Return the pending request when the typed request code matches; nothing is written.

    A mismatch raises request_code_mismatch; the request stays pending.
    """
    session = await pending_session(db, session_id)
    if not typed_code_matches(typed, session.code_challenge):
        raise TokenValidationError(CODE_MISMATCH)
    return session


async def approve_session(
    db: AsyncSession, session_id: UUID, user: User, typed: str
) -> tuple[CliAuthSession, str]:
    """Bind a pending request in an allowed mode to the active user's session version once.

    The typed request code is checked first.
    """
    await check_request_code(db, session_id, typed)
    version = user.session_version
    current = await db.get(
        User, user.id, populate_existing=True, with_for_update={"key_share": True}
    )
    if current is None or not current.is_active or current.session_version != version:
        raise TokenValidationError(INACTIVE_OR_CHANGED_USER)
    code = secrets.token_urlsafe(32)
    result = await db.execute(
        update(CliAuthSession)
        .where(*pending_conditions(session_id))
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


async def deny_session(db: AsyncSession, session_id: UUID) -> CliAuthSession:
    """Delete a pending request once and return the deleted row."""
    result = await db.execute(
        delete(CliAuthSession).where(*pending_conditions(session_id)).returning(CliAuthSession)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise TokenValidationError(NOT_PENDING)
    return session


def loopback_target(session: CliAuthSession, name: str, value: str) -> str:
    """Append one parameter and the original state to the validated loopback URI."""
    target = urlsplit(session.redirect_uri)
    query = parse_qsl(target.query, keep_blank_values=True) + [
        (name, value),
        ("state", session.state),
    ]
    return urlunsplit(target._replace(query=urlencode(query)))


def callback_target(session: CliAuthSession, code: str) -> str:
    """Append the approved code and original state to the validated loopback URI."""
    return loopback_target(session, "code", code)


def denial_target(session: CliAuthSession) -> str:
    """Append error=access_denied and the original state to the validated loopback URI."""
    return loopback_target(session, "error", "access_denied")


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
    """Consume an approved request once after checking its mode, the code, proof key and account."""
    session = await db.get(CliAuthSession, session_id)
    if session is not None and code_mode_refused(session.mode):
        raise CodeModeDisabledError()
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
