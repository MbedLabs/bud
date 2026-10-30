"""Audit log responses."""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, field_serializer


class AuditEventResponse(BaseModel):
    """One audit event, with the acting user's name when the user still exists.

    ``target_label``, ``created_label`` and ``station_name`` name the target, the object a
    ``201`` answer created and the acting Test Station; the matching ``*_deleted`` flag is true
    when that object is deleted. They stay empty for a kind without a name.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    occurred_at: datetime
    actor_user_id: Optional[int] = None
    actor_name: Optional[str] = None
    actor_profile_picture_url: Optional[str] = None
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
    target_label: Optional[str] = None
    target_deleted: bool = False
    created_label: Optional[str] = None
    created_deleted: bool = False
    station_name: Optional[str] = None
    station_deleted: bool = False

    @field_serializer("occurred_at")
    def serialize_dt(self, dt: Optional[datetime], _info):
        return f"{dt.isoformat()}Z" if dt else None


class AuditEventPage(BaseModel):
    """A page of audit events, newest first, and the total that match the filter."""

    items: List[AuditEventResponse]
    total: int
