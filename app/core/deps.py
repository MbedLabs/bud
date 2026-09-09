"""Shared FastAPI dependencies."""

from fastapi import Depends, Header, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.runner_auth import authenticate_runner_token
from app.core.runner_keys import resolve_key
from app.core.security import oauth2_scheme
from app.db import get_db
from app.models import Runner, RunnerApiKey

# ── Rate limiter (H2) ──────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── Auth Dependencies ──────────────────────────────────────────────────────────


async def get_current_runner(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> Runner:
    """M3: Authenticate a runner via JWT."""
    runner = await authenticate_runner_token(token, db)
    if not runner:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return runner


# ── API-key auth (C2) ─────────────────────────────────────────────────────────


async def require_runner_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> RunnerApiKey:
    """C2: Resolve the enrolment key presented for a runner-registration mutation."""
    record = await resolve_key(x_api_key, db)
    if record is None:
        raise HTTPException(status_code=403, detail="Invalid API key.")
    return record
