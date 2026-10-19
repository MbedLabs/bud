"""Audit log API for users with ``audit.view``: read the audit events, newest first, with filters.

There is no endpoint that changes or deletes an event.
"""

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

router = APIRouter()

require_admin = require_permission("audit", "view")


@router.get("", response_model=AuditEventPage)
async def list_audit_events(
    actor_user_id: Optional[int] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    product_id: Optional[int] = None,
    outcome: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_admin),
):
    """List audit events matching every given filter; an action filter ending in "." is a prefix."""
    conditions = []
    if actor_user_id is not None:
        conditions.append(AuditEvent.actor_user_id == actor_user_id)
    if action:
        if action.endswith("."):
            conditions.append(AuditEvent.action.startswith(action))
        else:
            conditions.append(AuditEvent.action == action)
    if target_type:
        conditions.append(AuditEvent.target_type == target_type)
    if target_id:
        conditions.append(AuditEvent.target_id == target_id)
    if product_id is not None:
        conditions.append(AuditEvent.product_id == product_id)
    if outcome:
        conditions.append(AuditEvent.outcome == outcome)
    if since is not None:
        conditions.append(AuditEvent.occurred_at >= since)
    if until is not None:
        conditions.append(AuditEvent.occurred_at < until)

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
    items = []
    for event, actor in rows:
        item = AuditEventResponse.model_validate(event)
        item.actor_name = actor.full_name if actor else None
        item.actor_profile_picture_url = actor.profile_picture_url if actor else None
        items.append(item)
    return AuditEventPage(items=items, total=total or 0)
