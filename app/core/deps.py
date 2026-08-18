"""
Shared FastAPI dependencies.

C2: API key authentication for endpoints that create/mutate sensitive resources.
H2: Rate limiting via slowapi.
"""

import hmac

from fastapi import Depends, Header, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.runner_auth import (
    authenticate_runner_token,
    authenticate_teststation_token,
)
from app.core.security import oauth2_scheme
from app.db import get_db
from app.models import Runner, TestStation

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
    runner = await authenticate_runner_token(token, db)
    if not runner:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return runner


async def get_current_teststation(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> TestStation:
    """Authenticate the active test station named by a teststation JWT."""
    teststation = await authenticate_teststation_token(token, db)
    if teststation is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return teststation


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
    # Constant-time comparison so the key can't be guessed via timing differences.
    if not hmac.compare_digest(x_api_key.encode(), expected.encode()):
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
    # Constant-time comparison so the key can't be guessed via timing differences.
    if not hmac.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Invalid API key.")
