"""Shared FastAPI dependencies."""

import os
import warnings

from fastapi import Depends, Header, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.runner_auth import authenticate_runner_token
from app.core.runner_keys import resolve_key
from app.core.security import oauth2_scheme
from app.db import get_db
from app.models import Runner, RunnerApiKey
from app.services.audit import set_audit_actor


def _build_limiter() -> Limiter:
    """Build the rate limiter, giving it no dotenv file when dotenv loading is disabled."""
    if os.environ.get("BUD_DOTENV_DISABLED") != "1":
        return Limiter(key_func=get_remote_address)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Config file .* not found", category=UserWarning)
        return Limiter(key_func=get_remote_address, config_filename=os.devnull)


limiter = _build_limiter()


async def get_current_runner(
    db: AsyncSession = Depends(get_db, scope="function"), token: str = Depends(oauth2_scheme)
) -> Runner:
    """M3: Authenticate a runner via JWT and record the station as the request's actor."""
    runner = await authenticate_runner_token(token, db)
    if not runner:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    set_audit_actor("runner", runner_id=runner.id)
    return runner


async def require_runner_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> RunnerApiKey:
    """C2: Resolve the enrolment key presented for a runner-registration mutation.

    A key bound to a station records that station as the request's actor.
    """
    record = await resolve_key(x_api_key, db)
    if record is None:
        raise HTTPException(status_code=403, detail="Invalid API key.")
    if record.runner_id is not None:
        set_audit_actor("runner", runner_id=record.runner_id)
    return record
