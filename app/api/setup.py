"""
First-run setup: create the very first administrator.

A packaged install (Cloudron, or any one-click deployment) has no way to ask the
operator for an email address at install time, and no safe place to put a
generated password. Instead the instance comes up with an empty user table and
asks the first visitor to create the administrator account.

Both endpoints are unauthenticated, which is only safe because they refuse to
act once any user exists: the window is exactly the gap between first boot and
first sign-up, and it closes permanently.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import limiter
from app.core.security import get_password_hash
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.auth import GenericMessageResponse
from app.schemas.setup import CreateFirstAdminRequest, SetupStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Arbitrary but fixed: the key identifies "the Bud first-admin bootstrap" to
# PostgreSQL's advisory lock namespace, and must not change between releases.
_SETUP_LOCK_KEY = 8_314_502_119


async def _user_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(User))
    return int(result.scalar_one())


@router.get("/setup/status", response_model=SetupStatusResponse)
async def setup_status(db: AsyncSession = Depends(get_db)) -> SetupStatusResponse:
    """Report whether the instance still needs its first administrator.

    The UI calls this before rendering the login screen, so it can send a brand
    new instance to the setup form instead.
    """
    return SetupStatusResponse(setup_required=await _user_count(db) == 0)


@router.post(
    "/setup",
    response_model=GenericMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
async def create_first_admin(
    request: Request,
    data: CreateFirstAdminRequest,
    db: AsyncSession = Depends(get_db),
) -> GenericMessageResponse:
    """Create the first administrator, once, on an instance that has no users."""
    # Serialise concurrent attempts so two simultaneous requests cannot both see
    # an empty table and both create an administrator. The lock is held to the
    # end of this transaction. SQLite (unit tests) has no equivalent and needs
    # none: its writes are already serialised.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _SETUP_LOCK_KEY})

    if await _user_count(db) > 0:
        # Not 403: the request was well-formed and authorised, the instance has
        # simply moved past the state in which it is meaningful.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This instance has already been set up.",
        )

    admin = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(admin)
    await db.commit()

    logger.info("First administrator created via setup flow: %s", data.email)
    return GenericMessageResponse(message="Administrator account created. You can now sign in.")
