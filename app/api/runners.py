"""
Runners API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.db import get_db
from app.models import Runner
from app.schemas import RunnerRegister, RunnerResponse, RunnerToken, RunnerHeartbeat
from app.core.security import get_password_hash, generate_runner_token

router = APIRouter()


@router.post("/register", response_model=RunnerToken, status_code=201)
async def register_runner(
    data: RunnerRegister,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new test runner.
    
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
async def runner_heartbeat(
    data: RunnerHeartbeat,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a heartbeat from a runner.
    
    Updates the last_heartbeat timestamp for the runner.
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
):
    """
    Get status of all runners.
    """
    result = await db.execute(
        select(Runner).order_by(Runner.last_heartbeat.desc())
    )
    runners = result.scalars().all()
    
    # Check for stale runners
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


@router.delete("/{account}", status_code=204)
async def delete_runner(
    account: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a runner.
    """
    result = await db.execute(
        select(Runner).where(Runner.account == account)
    )
    runner = result.scalar_one_or_none()
    
    if not runner:
        raise HTTPException(status_code=404, detail="Runner not found")
    
    await db.delete(runner)
