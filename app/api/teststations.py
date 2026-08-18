"""
TestStations API endpoints.

H2: Rate-limited registration and heartbeat endpoints.
C2: TestStation registration requires a server-side API key.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_role
from app.core.config import settings
from app.core.deps import get_current_teststation, limiter, require_teststation_api_key
from app.core.security import (
    generate_teststation_token,
    get_password_hash,
    verify_password,
)
from app.db import get_db
from app.models import TestStation
from app.models.user import User, UserRole
from app.schemas import (
    TestStationHeartbeat,
    TestStationRegister,
    TestStationResponse,
    TestStationStatusList,
    TestStationToken,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=TestStationToken,
    status_code=201,
    dependencies=[Depends(require_teststation_api_key)],
)
@limiter.limit("10/minute")  # H2: prevent registration flood
async def register_teststation(
    request: Request,
    data: TestStationRegister,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new test station.

    Requires a valid X-API-Key header (C2).
    Rate-limited to 10 requests/minute per IP (H2).
    Creates a teststation account and returns an authentication token.
    """
    # Check if teststation already exists
    result = await db.execute(select(TestStation).where(TestStation.account == data.username))
    existing = result.scalar_one_or_none()

    token = generate_teststation_token(data.username)
    if existing:
        if not verify_password(data.password, existing.password_hash):
            raise HTTPException(
                status_code=400,
                detail="TestStation already exists and password does not match.",
            )
        teststation = existing
        teststation.token = token
        teststation.socket_port = data.socket_port
        teststation.location = data.location
        teststation.is_active = True
    else:
        teststation = TestStation(
            account=data.username,
            password_hash=get_password_hash(data.password),
            token=token,
            socket_port=data.socket_port,
            location=data.location,
        )
        db.add(teststation)
    await db.flush()
    await db.refresh(teststation)

    return TestStationToken(
        account=teststation.account,
        token=token,
    )


@router.post("/heartbeat")
@limiter.limit("60/minute")  # H2: allow frequent heartbeats but cap abuse
async def teststation_heartbeat(
    request: Request,
    data: TestStationHeartbeat,
    db: AsyncSession = Depends(get_db),
    current_teststation: TestStation = Depends(get_current_teststation),
):
    """
    Receive a heartbeat from a test station.

    Updates the last_heartbeat timestamp for the teststation.
    Rate-limited to 60 requests/minute per IP (H2).
    """
    if current_teststation.account != data.teststation_account:
        raise HTTPException(
            status_code=403,
            detail="You can only send heartbeats for your own teststation account.",
        )

    current_teststation.last_heartbeat = datetime.utcnow()
    current_teststation.is_active = True
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "account": current_teststation.account,
    }


@router.get("/status", response_model=TestStationStatusList)
async def get_teststation_status(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Get status of all teststations.
    """
    result = await db.execute(select(TestStation).order_by(TestStation.last_heartbeat.desc()))
    teststations = result.scalars().all()

    timeout = timedelta(seconds=settings.RUNNER_HEARTBEAT_TIMEOUT)
    now = datetime.utcnow()

    teststation_list = []
    for teststation in teststations:
        is_online = False
        if teststation.last_heartbeat:
            is_online = (now - teststation.last_heartbeat) < timeout

        teststation_list.append(
            {
                "id": teststation.id,
                "account": teststation.account,
                "socket_port": teststation.socket_port,
                "location": teststation.location,
                "is_active": teststation.is_active,
                "last_heartbeat": teststation.last_heartbeat,
                "created_at": teststation.created_at,
                "is_online": is_online,
            }
        )

    return {"teststations": teststation_list}


@router.get("/{account}", response_model=TestStationResponse)
async def get_teststation(
    account: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Get a test station by account name.
    """
    result = await db.execute(select(TestStation).where(TestStation.account == account))
    teststation = result.scalar_one_or_none()

    if not teststation:
        raise HTTPException(status_code=404, detail="TestStation not found")

    return teststation


@router.delete("/{account}", status_code=204)
async def delete_teststation(
    account: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """
    Delete a test station. Requires an authenticated administrator.
    """
    result = await db.execute(select(TestStation).where(TestStation.account == account))
    teststation = result.scalar_one_or_none()

    if not teststation:
        raise HTTPException(status_code=404, detail="TestStation not found")

    await db.delete(teststation)
