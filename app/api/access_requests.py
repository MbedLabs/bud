"""Access requests: a signed-in user who is refused a resource asks the administrators.

The request names the resource only by the type and id the user already saw in the
address; nothing about the resource is looked up or disclosed. One
request per user and resource per 24 hours; the administrators are emailed and the
request, its grant or its refusal are recorded in the audit log.
"""

from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_role
from app.core.config import settings
from app.core.observability import request_id_var
from app.db.database import get_db
from app.models.access_request import AccessRequest
from app.models.user import User, UserRole
from app.services.audit import record_audit_event
from app.services.mail_service import MailConfigurationError, send_access_request_email

router = APIRouter()

require_admin = require_role(UserRole.admin)

REQUEST_WINDOW = timedelta(hours=24)

ResourceType = Literal["test-run", "product"]


class AccessRequestCreate(BaseModel):
    """What the user asks access to, as shown in the address they opened."""

    resource_type: ResourceType
    resource_ref: str = Field(..., min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")


class AccessRequestResponse(BaseModel):
    """A request, as its requester or an administrator sees it."""

    id: int
    resource_type: str
    resource_ref: str
    status: str
    created_at: datetime
    decided_at: Optional[datetime] = None
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    already_requested: bool = False
    mail_sent: Optional[bool] = None


class AccessDecision(BaseModel):
    """An administrator's answer to a pending request."""

    decision: Literal["granted", "refused"]


def _response(row: AccessRequest, user: Optional[User] = None, **extra) -> AccessRequestResponse:
    return AccessRequestResponse(
        id=row.id,
        resource_type=row.resource_type,
        resource_ref=row.resource_ref,
        status=row.status,
        created_at=row.created_at,
        decided_at=row.decided_at,
        requester_name=user.full_name if user else None,
        requester_email=user.email if user else None,
        **extra,
    )


async def _recent_request(
    db: AsyncSession,
    user_id: int,
    resource_type: str,
    resource_ref: str,
) -> Optional[AccessRequest]:
    """The user's request for this resource from the last 24 hours, if any."""
    query = (
        select(AccessRequest)
        .where(
            AccessRequest.user_id == user_id,
            AccessRequest.resource_type == resource_type,
            AccessRequest.resource_ref == resource_ref,
            AccessRequest.created_at >= datetime.utcnow() - REQUEST_WINDOW,
        )
        .order_by(AccessRequest.created_at.desc())
        .limit(1)
    )
    return (await db.execute(query)).scalar_one_or_none()


def _review_link() -> str:
    """Where an administrator grants the access: the users page, groups and product grants."""
    return f"{settings.APP_BASE_URL.rstrip('/')}/users"


@router.post("", response_model=AccessRequestResponse, status_code=201)
async def request_access(
    data: AccessRequestCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    """Ask the administrators for access; a repeat within 24 hours returns the first request."""
    existing = await _recent_request(db, current_user.id, data.resource_type, data.resource_ref)
    if existing is not None:
        response.status_code = 200
        return _response(existing, already_requested=True)

    row = AccessRequest(
        user_id=current_user.id,
        resource_type=data.resource_type,
        resource_ref=data.resource_ref,
        status="pending",
    )
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        "access.requested",
        target_type=data.resource_type,
        target_id=data.resource_ref,
        details={"access_request_id": row.id},
    )

    admins = (
        (
            await db.execute(
                select(User).where(User.role == UserRole.admin, User.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    resource = data.resource_ref
    mail_sent = bool(admins)
    for admin in admins:
        try:
            send_access_request_email(
                to_email=admin.email,
                admin_name=admin.full_name,
                requester_name=current_user.full_name,
                requester_email=current_user.email,
                resource=resource,
                project="",
                requested_at=row.created_at.strftime("%Y-%m-%d %H:%M UTC"),
                request_id=request_id_var.get(),
                review_link=_review_link(),
            )
        except MailConfigurationError:
            mail_sent = False
    return _response(row, mail_sent=mail_sent)


@router.get("/mine", response_model=Optional[AccessRequestResponse])
async def my_access_request(
    resource_type: ResourceType,
    resource_ref: str = Query(..., min_length=1, max_length=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    """The user's own request for this resource from the last 24 hours, or null."""
    row = await _recent_request(db, current_user.id, resource_type, resource_ref)
    return _response(row, already_requested=True) if row else None


@router.get("", response_model=list[AccessRequestResponse])
async def list_access_requests(
    status: Optional[Literal["pending", "granted", "refused"]] = "pending",
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    """Access requests for administrators, newest first."""
    query = (
        select(AccessRequest, User)
        .join(User, User.id == AccessRequest.user_id)
        .order_by(AccessRequest.created_at.desc())
    )
    if status:
        query = query.where(AccessRequest.status == status)
    return [_response(row, user) for row, user in (await db.execute(query)).all()]


@router.post("/{request_id}/decision", response_model=AccessRequestResponse)
async def decide_access_request(
    request_id: int,
    data: AccessDecision,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    """Record the administrator's grant or refusal against a pending request."""
    row = await db.get(AccessRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Access request not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="This request was already answered")
    row.status = data.decision
    row.decided_by_user_id = admin.id
    row.decided_at = datetime.utcnow()
    await record_audit_event(
        db,
        f"access.{data.decision}",
        target_type=row.resource_type,
        target_id=row.resource_ref,
        details={
            "access_request_id": row.id,
            "requester_user_id": row.user_id,
        },
    )
    requester = await db.get(User, row.user_id)
    return _response(row, requester)
