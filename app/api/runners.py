"""
Runners API endpoints.

H2: Rate-limited registration and heartbeat endpoints.
C2: Runner registration requires a server-side API key.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.db import get_db
from app.models import Runner
from app.schemas import RunnerRegister, RunnerResponse, RunnerToken, RunnerHeartbeat
from app.core.security import get_password_hash, generate_runner_token
from app.core.deps import limiter, require_runner_api_key
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/register", response_model=RunnerToken, status_code=201,
             dependencies=[Depends(require_runner_api_key)])
@limiter.limit("10/minute")  # H2: prevent registration flood
async def register_runner(
    request: Request,
    data: RunnerRegister,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new test runner.

    Requires a valid X-API-Key header (C2).
    Rate-limited to 10 requests/minute per IP (H2).
    Creates a runner account and returns an authentication token.
    """
    # Check if runner already exists
    result = await db.execute(
        select(Runner).where(Runner.account == data.username)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Runner with this account name already exists",
        )

    # Generate token
    token = generate_runner_token(data.username)

    # Create runner
    runner = Runner(
        account=data.username,
        password_hash=get_password_hash(data.password),
        token=token,
        socket_port=data.socket_port,
        location=data.location,
    )

    db.add(runner)
    await db.flush()
    await db.refresh(runner)

    return RunnerToken(
        account=runner.account,
        token=token,
    )


@router.post("/heartbeat")
@limiter.limit("60/minute")  # H2: allow frequent heartbeats but cap abuse
async def runner_heartbeat(
    request: Request,
    data: RunnerHeartbeat,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a heartbeat from a runner.

    Updates the last_heartbeat timestamp for the runner.
    Rate-limited to 60 requests/minute per IP (H2).
    """
    result = await db.execute(
        select(Runner).where(Runner.account == data.runner_account)
    )
    runner = result.scalar_one_or_none()

    if not runner:
        raise HTTPException(status_code=404, detail="Runner not found")

    runner.last_heartbeat = datetime.utcnow()
    runner.is_active = True

    await db.flush()

    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/status")
async def get_runner_status(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Get status of all runners.
    """
    result = await db.execute(
        select(Runner).order_by(Runner.last_heartbeat.desc())
    )
    runners = result.scalars().all()

    from app.core.config import settings
    from datetime import timedelta

    timeout = timedelta(seconds=settings.RUNNER_HEARTBEAT_TIMEOUT)
    now = datetime.utcnow()

    runner_list = []
    for runner in runners:
        is_online = False
        if runner.last_heartbeat:
            is_online = (now - runner.last_heartbeat) < timeout

        runner_list.append({
            "account": runner.account,
            "is_online": is_online,
            "is_active": runner.is_active,
            "last_heartbeat": runner.last_heartbeat.isoformat() if runner.last_heartbeat else None,
            "socket_port": runner.socket_port,
            "location": runner.location,
        })

    return {"runners": runner_list}


@router.get("/{account}", response_model=RunnerResponse)
async def get_runner(
    account: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Get a runner by account name.
    """
    result = await db.execute(
        select(Runner).where(Runner.account == account)
    )
    runner = result.scalar_one_or_none()

    if not runner:
        raise HTTPException(status_code=404, detail="Runner not found")

    return runner


@router.delete("/{account}", status_code=204,
               dependencies=[Depends(require_runner_api_key)])
async def delete_runner(
    request: Request,
    account: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a runner. Requires X-API-Key (C2).
    """
    result = await db.execute(
        select(Runner).where(Runner.account == account)
    )
    runner = result.scalar_one_or_none()

    if not runner:
        raise HTTPException(status_code=404, detail="Runner not found")

    await db.delete(runner)
