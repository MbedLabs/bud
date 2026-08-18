"""
Runner and Test Station JWT authentication with heartbeat-backed expiry bypass.

Runner tokens are minted with a fixed ``exp`` at registration. Heartbeat does not
re-issue the JWT. For long-lived daemons, an expired runner JWT remains valid for
API access while ``last_heartbeat`` is within ``RUNNER_HEARTBEAT_TIMEOUT``.
"""

import hmac
from datetime import datetime, timedelta
from typing import Optional, TypeVar, cast

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import ALGORITHM, decode_access_token
from app.models import Runner, TestStation

MachineEntity = TypeVar("MachineEntity", Runner, TestStation)


def decode_access_token_ignore_exp(token: str) -> Optional[dict]:
    """Decode a JWT verifying signature but not expiration."""
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": False},
        )
    except JWTError:
        return None


def runner_has_recent_heartbeat(
    runner: Runner | TestStation,
    now: Optional[datetime] = None,
) -> bool:
    """True when the runner reported a heartbeat within the configured timeout."""
    if runner.last_heartbeat is None:
        return False
    now = now or datetime.utcnow()
    last = runner.last_heartbeat
    if last.tzinfo is not None:
        last = last.replace(tzinfo=None)
    return (now - last) < timedelta(seconds=settings.RUNNER_HEARTBEAT_TIMEOUT)


async def _authenticate_machine_token(
    token: str,
    db: AsyncSession,
    *,
    token_type: str,
    model: type[MachineEntity],
) -> Optional[MachineEntity]:
    payload = decode_access_token(token)
    require_recent_heartbeat = False
    if not payload:
        payload = decode_access_token_ignore_exp(token)
        require_recent_heartbeat = True
    if not payload or payload.get("type") != token_type:
        return None

    account = payload.get("sub")
    if not account:
        return None

    result = await db.execute(select(model).where(model.account == account))
    entity = result.scalar_one_or_none()
    if (
        not entity
        or not entity.is_active
        or not entity.token
        or not hmac.compare_digest(entity.token, token)
    ):
        return None
    if require_recent_heartbeat and not runner_has_recent_heartbeat(entity):
        return None
    return entity


async def authenticate_runner_token(token: str, db: AsyncSession) -> Optional[Runner]:
    """Resolve the active runner holding the current stored bearer token."""

    entity = await _authenticate_machine_token(token, db, token_type="runner", model=Runner)
    return cast(Optional[Runner], entity)


async def authenticate_teststation_token(token: str, db: AsyncSession) -> Optional[TestStation]:
    """Resolve the active Test Station holding the current stored bearer token."""

    entity = await _authenticate_machine_token(
        token, db, token_type="teststation", model=TestStation
    )
    return cast(Optional[TestStation], entity)
