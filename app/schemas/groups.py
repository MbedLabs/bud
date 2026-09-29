"""Schemas for the admin groups API."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_serializer

GroupRole = Literal["developer", "viewer"]


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    role: GroupRole = "viewer"


class GroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    role: Optional[GroupRole] = None


class GroupMemberAdd(BaseModel):
    user_id: int


class GroupMemberResponse(BaseModel):
    user_id: int
    email: str
    full_name: str


class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    role: str
    members: list[GroupMemberResponse]
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, dt: Optional[datetime], _info):
        return f"{dt.isoformat()}Z" if dt else None
