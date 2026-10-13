"""Schemas for the access API: policies, groups and the users they are given to."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.user import UserRole


def _trim(value):
    """Trim a name before validating its length."""
    return value.strip() if isinstance(value, str) else value


class _Timestamped(BaseModel):
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, dt: Optional[datetime], _info):
        return f"{dt.isoformat()}Z" if dt else None


class PolicyCreate(BaseModel):
    """A custom policy: a name and the actions it grants per resource."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    permissions: dict[str, list[str]] = Field(default_factory=dict)

    _trim_name = field_validator("name", mode="before")(_trim)


class PolicyUpdate(BaseModel):
    """Changes to a custom policy."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    permissions: Optional[dict[str, list[str]]] = None

    _trim_name = field_validator("name", mode="before")(_trim)


class PolicyResponse(_Timestamped):
    id: int
    name: str
    description: Optional[str] = None
    permissions: dict[str, list[str]]
    is_default: bool
    system_key: Optional[str] = None


class CatalogueResource(BaseModel):
    resource: str
    actions: list[str]


class GroupCreate(BaseModel):
    """A custom group: a name and the policies it bundles."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    policy_ids: list[int] = Field(default_factory=list)

    _trim_name = field_validator("name", mode="before")(_trim)


class GroupUpdate(BaseModel):
    """Changes to a custom group."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    policy_ids: Optional[list[int]] = None

    _trim_name = field_validator("name", mode="before")(_trim)


class GroupMemberAdd(BaseModel):
    user_id: int


class GroupMemberResponse(BaseModel):
    user_id: int
    email: str
    full_name: str
    role: UserRole
    profile_picture_url: Optional[str] = None


class GroupPolicyRef(BaseModel):
    id: int
    name: str


class GroupResponse(_Timestamped):
    id: int
    name: str
    description: Optional[str] = None
    is_default: bool
    system_key: Optional[str] = None
    policies: list[GroupPolicyRef]
    permissions: list[str]
    members: list[GroupMemberResponse]


class AccessGroupRef(BaseModel):
    id: int
    name: str


class AccessUserResponse(BaseModel):
    """A user as access management sees them: base role, groups and effective access."""

    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    groups: list[AccessGroupRef]
    permissions: list[str]
    profile_picture_url: Optional[str] = None
