"""Access requests: a signed-in user asks the administrators for access to a resource."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AccessRequest(Base):
    """One request for one resource; its status becomes granted or refused by an administrator."""

    __tablename__ = "access_requests"
    __table_args__ = (
        Index("ix_access_requests_lookup", "user_id", "resource_type", "resource_ref"),
        Index("ix_access_requests_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(30), nullable=False)
    resource_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    decided_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
