"""First-run setup: create the very first administrator."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import limiter
from app.core.security import get_password_hash
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.setup import (
    CreateFirstAdminRequest,
    SetupCompletedResponse,
    SetupStatusResponse,
)
from app.services.mail_service import MailConfigurationError, send_admin_welcome_email

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
    """Report whether the instance still needs its first administrator."""
    return SetupStatusResponse(setup_required=await _user_count(db) == 0)


@router.post(
    "/setup",
    response_model=SetupCompletedResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
async def create_first_admin(
    request: Request,
    data: CreateFirstAdminRequest,
    db: AsyncSession = Depends(get_db),
) -> SetupCompletedResponse:
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

    # Best effort, never fatal. Setup must complete on a deployment with no SMTP at all
    # — the docker-compose default, and any Cloudron install with the optional mail
    # addon disabled.
    try:
        send_admin_welcome_email(
            to_email=admin.email,
            full_name=admin.full_name,
            login_link=f"{settings.FRONTEND_BASE_URL.rstrip('/')}/login",
        )
    except MailConfigurationError as exc:
        logger.warning("Administrator created but the confirmation email failed: %s", exc)

    return SetupCompletedResponse(
        message="Administrator account created. You can now sign in.",
    )
