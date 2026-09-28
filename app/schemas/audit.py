"""Audit log responses."""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, field_serializer


class AuditEventResponse(BaseModel):
    """One audit event, with the acting user's name when the user still exists."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    occurred_at: datetime
    actor_user_id: Optional[int] = None
    actor_name: Optional[str] = None
    actor_type: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    product_id: Optional[int] = None
    request_id: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    outcome: str
    details: Optional[dict[str, Any]] = None

    @field_serializer("occurred_at")
    def serialize_dt(self, dt: Optional[datetime], _info):
        return f"{dt.isoformat()}Z" if dt else None


class AuditEventPage(BaseModel):
    """A page of audit events, newest first, and the total that match the filter."""

    items: List[AuditEventResponse]
    total: int
