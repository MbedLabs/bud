"""
User model and role enum.
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime
from sqlalchemy import Enum as SaEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SaEnum(UserRole), default=UserRole.viewer, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Bumped on password change/reset and confirmed email change. Every access
    # token carries the value it was minted with; a mismatch means the token
    # predates a credential change and is rejected, so those events log the user
    # out everywhere.
    session_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    invited_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    invited_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    last_invite_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    invite_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    password_set_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
