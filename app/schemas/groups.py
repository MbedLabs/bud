"""Schemas for the admin groups API."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_serializer


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    role: Literal["admin", "viewer"] = "viewer"


class GroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    role: Optional[Literal["admin", "viewer"]] = None


class GroupMemberAdd(BaseModel):
    user_id: int


class GroupGrantAdd(BaseModel):
    product_id: Optional[int] = None


class GroupMemberResponse(BaseModel):
    user_id: int
    email: str
    full_name: str


class GroupGrantResponse(BaseModel):
    id: int
    product_id: Optional[int] = None
    product_name: Optional[str] = None


class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    role: str
    members: list[GroupMemberResponse]
    grants: list[GroupGrantResponse]
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, dt: Optional[datetime], _info):
        return f"{dt.isoformat()}Z" if dt else None
