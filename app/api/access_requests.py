"""Access requests: a signed-in user without Publish to Bloom asks for it from a run.

Only ``publish-to-bloom`` is accepted; stored requests of the earlier types ``test-run`` and
``product`` stay listed and can be decided. A holder of Publish to Bloom, an Admin always,
is refused with 409. One request per user and run per
24 hours. Admins and holders of access management other than the requester are emailed and
decide; granting gives the requester a group holding Publish to Bloom. Administrators see the
run or product name of each request. The request, its grant or its refusal are recorded in
the audit log.
"""

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_serializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_permission
from app.api.groups import give_group, load_group
from app.core.access import effective_permissions, group_permissions
from app.core.config import settings
from app.core.observability import request_id_var
from app.core.timestamps import second_utc
from app.db.database import get_db
from app.models.access_request import AccessRequest
from app.models.user import User, UserRole
from app.services.audit import record_audit_event
from app.services.mail_service import MailConfigurationError, send_access_request_email
from app.services.target_labels import LabelResolver, target_kind

router = APIRouter()

require_admin = require_permission("access", "manage")

REQUEST_WINDOW = timedelta(hours=24)

ResourceType = Literal["publish-to-bloom"]
PUBLISH_TO_BLOOM = "publish-to-bloom"
PUBLISH_PERMISSION = "bloom_publish.execute"
ALREADY_HELD = "You already hold Publish to Bloom, so there is nothing to request."


class AccessRequestCreate(BaseModel):
    """What the user asks access to, as shown in the address they opened."""

    resource_type: ResourceType
    resource_ref: str = Field(..., min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")


class AccessRequestResponse(BaseModel):
    """A request, as its requester or an administrator sees it.

    ``resource_label`` is the name of the run or product the request names, shown to
    administrators; ``resource_deleted`` is true when that object is deleted.
    """

    id: int
    resource_type: str
    resource_ref: str
    status: str
    created_at: datetime
    decided_at: Optional[datetime] = None
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    requester_profile_picture_url: Optional[str] = None
    already_requested: bool = False
    mail_sent: Optional[bool] = None
    resource_label: Optional[str] = None
    resource_deleted: bool = False

    @field_serializer("created_at", "decided_at")
    def serialize_dt(self, dt: Optional[datetime], _info):
        return f"{dt.isoformat()}Z" if dt else None


class AccessDecision(BaseModel):
    """The answer to a pending request; a grant of Publish to Bloom names the group given."""

    decision: Literal["granted", "refused"]
    group_id: Optional[int] = None


def _response(row: AccessRequest, user: Optional[User] = None, **extra) -> AccessRequestResponse:
    """The answer for one stored request, with its requester when given."""
    return AccessRequestResponse(
        id=row.id,
        resource_type=row.resource_type,
        resource_ref=row.resource_ref,
        status=row.status,
        created_at=row.created_at,
        decided_at=row.decided_at,
        requester_name=user.full_name if user else None,
        requester_email=user.email if user else None,
        requester_profile_picture_url=user.profile_picture_url if user else None,
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
            AccessRequest.created_at
            >= datetime.now(timezone.utc).replace(tzinfo=None) - REQUEST_WINDOW,
        )
        .order_by(AccessRequest.created_at.desc())
        .limit(1)
    )
    return (await db.execute(query)).scalar_one_or_none()


async def _labelled(
    db: AsyncSession, pairs: list[tuple[AccessRequest, Optional[User]]]
) -> list[AccessRequestResponse]:
    """The answers for stored requests, each with the name of the run or product it names."""
    labels = LabelResolver()
    for row, _user in pairs:
        labels.want(target_kind(row.resource_type), row.resource_ref)
    await labels.load(db)
    answers = []
    for row, user in pairs:
        label = labels.get(target_kind(row.resource_type), row.resource_ref)
        answers.append(
            _response(row, user, resource_label=label.name, resource_deleted=label.deleted)
        )
    return answers


async def _requested_resource(db: AsyncSession, resource_ref: str) -> str:
    """How the email names the request: Publish to Bloom and the number and name of the run."""
    labels = LabelResolver()
    labels.want("run", resource_ref)
    await labels.load(db)
    run = labels.get("run", resource_ref).name
    named = f"{resource_ref}: {run}" if run else resource_ref
    return f"Publish to Bloom (from test run {named})"


def _review_link() -> str:
    """Return the administrator's access-review page."""
    return f"{settings.APP_BASE_URL.rstrip('/')}/access"


@router.post(
    "",
    response_model=AccessRequestResponse,
    status_code=201,
    responses={409: {"description": HTTPStatus(409).phrase}},
)
async def request_access(
    data: AccessRequestCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    """Ask the administrators for Publish to Bloom; a repeat within 24 hours returns the first
    request, and a holder of Publish to Bloom is refused with 409."""
    if PUBLISH_PERMISSION in await effective_permissions(db, current_user):
        raise HTTPException(status_code=409, detail=ALREADY_HELD)
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

    admins = [
        user
        for user in (await db.execute(select(User).where(User.is_active.is_(True)))).scalars()
        if user.id != current_user.id
        and (
            user.role == UserRole.admin or "access.manage" in await effective_permissions(db, user)
        )
    ]
    resource = await _requested_resource(db, data.resource_ref)
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
                requested_at=second_utc(row.created_at),
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
    return await _labelled(db, [(row, user) for row, user in (await db.execute(query)).all()])


@router.post(
    "/{request_id}/decision",
    response_model=AccessRequestResponse,
    responses={
        403: {"description": HTTPStatus(403).phrase},
        404: {"description": HTTPStatus(404).phrase},
        409: {"description": HTTPStatus(409).phrase},
        422: {"description": HTTPStatus(422).phrase},
    },
)
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
    group_id = None
    if data.decision == "granted" and (
        data.group_id is not None or row.resource_type == PUBLISH_TO_BLOOM
    ):
        if data.group_id is None:
            raise HTTPException(
                status_code=422, detail="Choose the group that gives Publish to Bloom"
            )
        group = await load_group(db, data.group_id)
        if row.resource_type == PUBLISH_TO_BLOOM and (
            "bloom_publish.execute" not in group_permissions(group)
        ):
            raise HTTPException(status_code=422, detail="This group does not give Publish to Bloom")
        requester = await db.get(User, row.user_id)
        if requester is None:
            raise HTTPException(status_code=404, detail="User not found")
        await give_group(db, admin, group, requester)
        group_id = group.id
    row.status = data.decision
    row.decided_by_user_id = admin.id
    row.decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await record_audit_event(
        db,
        f"access.{data.decision}",
        target_type=row.resource_type,
        target_id=row.resource_ref,
        details={
            "access_request_id": row.id,
            "requester_user_id": row.user_id,
            "group_id": group_id,
        },
    )
    requester = await db.get(User, row.user_id)
    return (await _labelled(db, [(row, requester)]))[0]
