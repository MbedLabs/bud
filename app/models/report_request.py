"""Report requests received through the configured Bloom connection."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ReportRequest(Base):
    """A mirrored Bloom request, its decision and notified publisher IDs."""

    __tablename__ = "report_requests"
    __table_args__ = (UniqueConstraint("bloom_url", "remote_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bloom_url: Mapped[str] = mapped_column(String(500))
    remote_id: Mapped[int] = mapped_column(Integer)
    run_id: Mapped[int] = mapped_column(Integer, index=True)
    project_prefix: Mapped[str] = mapped_column(String(50))
    requester_name: Mapped[str] = mapped_column(String(255))
    requester_email: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    notified_user_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
