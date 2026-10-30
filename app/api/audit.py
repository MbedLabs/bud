"""Audit log API for users with ``audit.view``: read the audit events, newest first, with filters.

There is no endpoint that changes or deletes an event.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_permission
from app.db.database import get_db
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.audit import AuditEventPage, AuditEventResponse
from app.services.target_labels import LabelResolver, created_kind, target_kind

router = APIRouter()

require_admin = require_permission("audit", "view")


@dataclass
class AuditFilters:
    """The filters of the audit list, each a query parameter; every given filter must match.

    An action ending in "." is a prefix; ``status`` matches the HTTP status of api.request
    events.
    """

    actor_user_id: Optional[int] = None
    action: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    product_id: Optional[int] = None
    outcome: Optional[str] = None
    actor_type: Optional[str] = None
    ip: Optional[str] = None
    request_id: Optional[str] = None
    status: Optional[int] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None

    def conditions(self) -> list:
        """The SQL conditions of the given filters."""
        equal = [
            (AuditEvent.actor_user_id, self.actor_user_id),
            (AuditEvent.target_type, self.target_type or None),
            (AuditEvent.target_id, self.target_id or None),
            (AuditEvent.product_id, self.product_id),
            (AuditEvent.outcome, self.outcome or None),
            (AuditEvent.actor_type, self.actor_type or None),
            (AuditEvent.ip, self.ip or None),
            (AuditEvent.request_id, self.request_id or None),
            (AuditEvent.details["status"].as_integer(), self.status),
        ]
        conditions = [column == value for column, value in equal if value is not None]
        if self.action and self.action.endswith("."):
            conditions.append(AuditEvent.action.startswith(self.action))
        elif self.action:
            conditions.append(AuditEvent.action == self.action)
        if self.since is not None:
            conditions.append(AuditEvent.occurred_at >= self.since)
        if self.until is not None:
            conditions.append(AuditEvent.occurred_at < self.until)
        return conditions


@router.get("", response_model=AuditEventPage)
async def list_audit_events(
    filters: AuditFilters = Depends(),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_admin),
):
    """List audit events matching every given filter, newest first."""
    conditions = filters.conditions()

    total = await db.scalar(select(func.count(AuditEvent.id)).where(*conditions))
    rows = (
        await db.execute(
            select(AuditEvent, User)
            .outerjoin(User, User.id == AuditEvent.actor_user_id)
            .where(*conditions)
            .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    labels = LabelResolver()
    for event, _actor in rows:
        for kind, ref in _named(event):
            labels.want(kind, ref)
    await labels.load(db)
    items = []
    for event, actor in rows:
        item = AuditEventResponse.model_validate(event)
        item.actor_name = actor.full_name if actor else None
        item.actor_profile_picture_url = actor.profile_picture_url if actor else None
        target, created, station = (labels.get(kind, ref) for kind, ref in _named(event))
        item.target_label, item.target_deleted = target.name, target.deleted
        item.created_label, item.created_deleted = created.name, created.deleted
        item.station_name, item.station_deleted = station.name, station.deleted
        items.append(item)
    return AuditEventPage(items=items, total=total or 0)


def _named(event: AuditEvent) -> tuple[tuple, tuple, tuple]:
    """The kind and id of an event's target, of what its ``201`` answer created and of its
    acting Test Station."""
    details = event.details or {}
    if details.get("created_test_run_id") is not None:
        created = ("run", details["created_test_run_id"])
    else:
        created = (created_kind(details.get("route")), details.get("created_id"))
    return (
        (target_kind(event.target_type), event.target_id),
        created,
        ("station", details.get("runner_id")),
    )
