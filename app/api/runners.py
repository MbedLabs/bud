"""
Runners API endpoints.

H2: Rate-limited registration and heartbeat endpoints.
C2: Runner registration requires a server-side API key.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_role
from app.core.config import settings
from app.core.deps import get_current_runner, limiter, require_runner_api_key
from app.core.security import generate_runner_token, get_password_hash, verify_password
from app.db import get_db
from app.models import Runner, TestRun
from app.models.user import User, UserRole
from app.schemas import (
    RunnerHeartbeat,
    RunnerRegister,
    RunnerResponse,
    RunnerStatusList,
    RunnerToken,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=RunnerToken,
    status_code=201,
    dependencies=[Depends(require_runner_api_key)],
)
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
    result = await db.execute(select(Runner).where(Runner.account == data.username))
    runner = result.scalar_one_or_none()

    if runner:
        # If it exists, verify password (M3)
        if not verify_password(data.password, runner.password_hash):
            raise HTTPException(
                status_code=400,
                detail="Runner already exists and password does not match.",
            )
        # Update socket_port and location if provided
        runner.socket_port = data.socket_port
        if data.location:
            runner.location = data.location
    else:
        # Create new runner
        runner = Runner(
            account=data.username,
            password_hash=get_password_hash(data.password),
            socket_port=data.socket_port,
            location=data.location,
        )
        db.add(runner)

    # Generate fresh token
    token = generate_runner_token(data.username)
    runner.token = token

    await db.commit()
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
    current_runner: Runner = Depends(get_current_runner),
):
    """
    Receive a heartbeat from a runner.

    M3: Authenticated — only the owner of the account can update its heartbeat/location.
    """
    if current_runner.account != data.runner_account:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only send heartbeats for your own runner account.",
        )

    current_runner.last_heartbeat = datetime.utcnow()
    current_runner.is_active = True

    if data.location:
        current_runner.location = data.location

    await db.commit()

    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "account": current_runner.account,
    }


@router.get("/status", response_model=RunnerStatusList)
async def get_runner_status(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Get status of all runners.
    """
    result = await db.execute(select(Runner).order_by(Runner.last_heartbeat.desc()))
    runners = result.scalars().all()

    runner_ids = [r.id for r in runners]

    # Find any test run currently executing on each runner.
    active_runs_map: dict[int, dict] = {}
    if runner_ids:
        active_q = await db.execute(
            select(TestRun)
            .where(TestRun.status == "Running", TestRun.runner_id.in_(runner_ids))
            .order_by(TestRun.started_at.desc())
        )
        for run in active_q.scalars().all():
            if run.runner_id not in active_runs_map:
                active_runs_map[run.runner_id] = {"id": run.id, "name": run.name}

    timeout = timedelta(seconds=settings.RUNNER_HEARTBEAT_TIMEOUT)
    now = datetime.utcnow()

    runner_list = []
    for runner in runners:
        is_online = False
        if runner.last_heartbeat:
            is_online = (now - runner.last_heartbeat) < timeout

        entry: dict = {
            "id": runner.id,
            "account": runner.account,
            "socket_port": runner.socket_port,
            "location": runner.location,
            "is_active": runner.is_active,
            "last_heartbeat": runner.last_heartbeat,
            "created_at": runner.created_at,
            "is_online": is_online,
            "current_run": active_runs_map.get(runner.id),
        }
        runner_list.append(entry)

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
    result = await db.execute(select(Runner).where(Runner.account == account))
    runner = result.scalar_one_or_none()

    if not runner:
        raise HTTPException(status_code=404, detail="Runner not found")

    return runner


@router.delete("/{account}", status_code=204)
async def delete_runner(
    account: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """
    Delete a runner. Requires an authenticated administrator.
    """
    result = await db.execute(select(Runner).where(Runner.account == account))
    runner = result.scalar_one_or_none()

    if not runner:
        raise HTTPException(status_code=404, detail="Runner not found")

    await db.delete(runner)
