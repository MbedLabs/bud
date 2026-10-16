"""Policies and access groups.

A policy is a named, person-agnostic permission set over Bud's resources. An access group
is a named bundle of policies given to users; a user can have several. Shipped defaults
carry ``is_default`` and a ``system_key`` and are read-only.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

access_group_policies = Table(
    "access_group_policies",
    Base.metadata,
    Column(
        "group_id", Integer, ForeignKey("access_groups.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("policy_id", Integer, ForeignKey("policies.id"), primary_key=True),
)


class Policy(Base):
    """A named permission set, stored as ``{resource: [action, ...]}``."""

    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_key: Mapped[Optional[str]] = mapped_column(String(40), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    permissions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AccessGroup(Base):
    """A named bundle of policies given to users."""

    __tablename__ = "access_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_key: Mapped[Optional[str]] = mapped_column(String(40), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    policies: Mapped[List[Policy]] = relationship(secondary=access_group_policies)
    members: Mapped[List["AccessGroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class AccessGroupMember(Base):
    """A user given an access group."""

    __tablename__ = "access_group_members"

    group_id: Mapped[int] = mapped_column(
        ForeignKey("access_groups.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    group: Mapped[AccessGroup] = relationship(back_populates="members")
