"""
Shared FastAPI dependencies.

C2: API key authentication for endpoints that create/mutate sensitive resources.
H2: Rate limiting via slowapi.
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token, oauth2_scheme
from app.db import get_db
from app.models import Runner

# ── Rate limiter (H2) ──────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── Auth Dependencies ──────────────────────────────────────────────────────────


async def get_current_runner(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> Runner:
    """
    M3: Authenticate a runner via JWT.

    Extracts the runner account from the token 'sub' claim and verifies
    it exists and is active in the database.
    """
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    account = payload.get("sub")
    entity_type = payload.get("type")

    if not account or entity_type != "runner":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid runner token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(Runner).where(Runner.account == account))
    runner = result.scalar_one_or_none()

    if not runner:
        raise HTTPException(status_code=404, detail="Runner not found")

    if not runner.is_active:
        raise HTTPException(status_code=400, detail="Inactive runner")

    return runner


# ── API-key auth (C2) ─────────────────────────────────────────────────────────


async def require_runner_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    """
    C2: Require a shared API key for runner-registration mutations.

    The key is read from the RUNNER_API_KEY environment variable.
    Set it in .env alongside SECRET_KEY.
    """
    expected = getattr(settings, "RUNNER_API_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: RUNNER_API_KEY is not set.",
        )
    if x_api_key != expected:
        raise HTTPException(status_code=403, detail="Invalid API key.")


async def require_teststation_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    """
    C2: Require a shared API key for teststation-registration mutations.
    """
    expected = getattr(settings, "RUNNER_API_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: RUNNER_API_KEY is not set.",
        )
    if x_api_key != expected:
        raise HTTPException(status_code=403, detail="Invalid API key.")
