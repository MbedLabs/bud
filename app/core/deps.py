"""
Shared FastAPI dependencies.

C2: API key authentication for endpoints that create/mutate sensitive resources.
H2: Rate limiting via slowapi.
"""

from fastapi import Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# ── Rate limiter (H2) ──────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

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
