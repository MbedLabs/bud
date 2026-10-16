"""Human execution requests and exclusion of retained legacy queue placeholders."""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, event
from sqlalchemy.orm import Mapped, Session, mapped_column, with_loader_criteria

from app.db.database import Base
from app.models.models import TestRun

SET_NULL = "SET NULL"
TEST_RUNS_ID = "test_runs.id"


class ExecutionRequest(Base):
    """A test selection waiting for its station, linked to the execution after claim."""

    __tablename__ = "execution_requests"
    __table_args__ = (
        CheckConstraint("state IN ('queued', 'claimed')", name="ck_execution_request_state"),
        CheckConstraint(
            "(state = 'queued' AND claimed_run_id IS NULL) OR "
            "(state = 'claimed' AND claimed_run_id IS NOT NULL)",
            name="ck_execution_request_claim_link",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requested_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete=SET_NULL), nullable=True
    )
    runner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("runners.id", ondelete=SET_NULL), nullable=True, index=True
    )
    runner_account: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    selected_tests: Mapped[list] = mapped_column(JSON, nullable=False)
    source_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(TEST_RUNS_ID, ondelete=SET_NULL), nullable=True
    )
    source_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    claimed_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(TEST_RUNS_ID), nullable=True, unique=True
    )
    legacy_queue_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(TEST_RUNS_ID), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def _execution_records_only(execute_state):
    """Exclude retained request placeholders from ordinary execution queries."""
    if execute_state.is_select and not execute_state.execution_options.get(
        "include_legacy_requests"
    ):
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(TestRun, TestRun.record_kind == "execution", include_aliases=True)
        )


event.listen(Session, "do_orm_execute", _execution_records_only)
