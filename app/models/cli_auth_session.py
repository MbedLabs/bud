"""Short-lived browser approvals for PKCE-bound CLI authentication."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CliAuthSession(Base):
    """A pending client request and its single-use, hashed approval code."""

    __tablename__ = "cli_auth_sessions"
    __table_args__ = (CheckConstraint("mode IN ('callback', 'code')", name="ck_cli_auth_mode"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    client_name: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    redirect_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(128), nullable=False)
    exchange_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    approved_session_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
