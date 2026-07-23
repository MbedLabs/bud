import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime
from sqlalchemy import Enum as SaEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UserTokenPurpose(str, enum.Enum):
    invite = "invite"
    email_verification = "email_verification"
    password_reset = "password_reset"
    refresh = "refresh"
    email_change = "email_change"


class UserToken(Base):
    __tablename__ = "user_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    purpose: Mapped[UserTokenPurpose] = mapped_column(SaEnum(UserTokenPurpose), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
