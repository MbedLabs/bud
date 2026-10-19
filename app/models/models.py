"""
Database models for the bud TMP.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

ALL_DELETE_ORPHAN = "all, delete-orphan"
TEST_RUNS_ID = "test_runs.id"


class Product(Base):
    """Product/project being tested."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    test_runs: Mapped[List["TestRun"]] = relationship(back_populates="product")
    results: Mapped[List["TestResult"]] = relationship("TestResult", backref="product_ref")


class Runner(Base):
    """Test runner (test bench) registration.

    Its test runs and API keys carry no ORM cascade; deleting a runner clears them by
    statement.
    """

    __tablename__ = "runners"

    id: Mapped[int] = mapped_column(primary_key=True)
    account: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    token: Mapped[str] = mapped_column(String(500))
    socket_port: Mapped[int] = mapped_column(Integer, default=53035)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    test_runs: Mapped[List["TestRun"]] = relationship(back_populates="runner")
    api_keys: Mapped[List["RunnerApiKey"]] = relationship(back_populates="runner")


class RunnerApiKey(Base):
    """An enrolment key for a single Test Station.

    key_prefix holds the leading characters of the key, which tell keys apart in the key
    list.
    """

    __tablename__ = "runner_api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(12))
    station_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    runner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("runners.id", ondelete="CASCADE"), index=True, nullable=True
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    runner: Mapped[Optional["Runner"]] = relationship(back_populates="api_keys")


class TestRun(Base):
    """A test run execution.

    claim_id is the client-generated idempotency key that binds retries to one queue claim.
    selected_tests lists the explicit test cases of a custom run as importable module.Class
    paths.
    """

    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    test_case_list: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), default="Pending")
    record_kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="execution", server_default="execution"
    )

    url_test_software: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ref_test_software: Mapped[str] = mapped_column(String(100), default="main")

    url_software_under_test: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ref_software_under_test: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    passed_tests: Mapped[int] = mapped_column(Integer, default=0)
    failed_tests: Mapped[int] = mapped_column(Integer, default=0)
    skipped_tests: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    claim_id: Mapped[Optional[str]] = mapped_column(
        String(36), unique=True, index=True, nullable=True
    )
    claim_acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    runner_exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    runner_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    selected_tests: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    bloom_artefact_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bloom_artefact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bloom_artefact_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id"), index=True, nullable=True
    )
    runner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("runners.id"), index=True, nullable=True
    )

    product: Mapped[Optional["Product"]] = relationship(back_populates="test_runs")
    runner: Mapped[Optional["Runner"]] = relationship(back_populates="test_runs")
    results: Mapped[List["TestResult"]] = relationship(
        back_populates="test_run", cascade=ALL_DELETE_ORPHAN
    )
    artifacts: Mapped[List["Artifact"]] = relationship(
        back_populates="test_run", cascade=ALL_DELETE_ORPHAN
    )
    events: Mapped[List["TestRunEvent"]] = relationship(
        back_populates="test_run", cascade=ALL_DELETE_ORPHAN
    )


class TestRunEvent(Base):
    """System-visible execution and integration event for a test run."""

    __tablename__ = "test_run_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    test_run_id: Mapped[int] = mapped_column(ForeignKey(TEST_RUNS_ID), index=True, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="completed")
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[Optional[dict]] = mapped_column("event_metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    test_run: Mapped["TestRun"] = relationship(back_populates="events")


class TestResult(Base):
    """Result of a single test case execution.

    test_run_id is optional for results stored before their run exists.
    """

    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    test_class: Mapped[str] = mapped_column(String(255))
    test_method: Mapped[str] = mapped_column(String(255))
    passed: Mapped[bool] = mapped_column(Boolean)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assertions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    test_metadata: Mapped[Optional[dict]] = mapped_column("test_metadata", JSON, nullable=True)

    work_package_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    test_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(TEST_RUNS_ID), index=True, nullable=True
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id"), index=True, nullable=True
    )

    test_run: Mapped[Optional["TestRun"]] = relationship(back_populates="results")


class Artifact(Base):
    """Uploaded artifacts (traces, logs, etc.)."""

    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    test_case: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    test_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(TEST_RUNS_ID), nullable=True, index=True
    )

    test_run: Mapped[Optional["TestRun"]] = relationship(back_populates="artifacts")


class UploadLease(Base):
    """Persistent reservation used to serialize upload concurrency and quota."""

    __tablename__ = "upload_leases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    principal_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    test_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(TEST_RUNS_ID, ondelete="CASCADE"), nullable=True, index=True
    )
    reserved_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class UploadAttempt(Base):
    """Database-backed rolling upload-start rate-limit record."""

    __tablename__ = "upload_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    principal_key: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class SystemSetting(Base):
    """General system settings (integrations, keys, etc.)."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class CompanyLogo(Base):
    """Instance-wide company logo: an admin-uploaded customer logo for PDF reports."""

    __tablename__ = "company_logo"

    id: Mapped[int] = mapped_column(primary_key=True)
    logo: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    logo_content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    logo_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class NotificationChannel(Base):
    """An outbound chat or automation webhook that finished runs are posted to."""

    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    format: Mapped[str] = mapped_column(String(20))
    url_encrypted: Mapped[str] = mapped_column(Text)
    url_prefix: Mapped[str] = mapped_column(String(60))
    secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    run_filter: Mapped[str] = mapped_column(String(30), default="all")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class NotificationDelivery(Base):
    """One attempt to post a run summary to a notification channel."""

    __tablename__ = "notification_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    test_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(TEST_RUNS_ID, ondelete="CASCADE"), nullable=True, index=True
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("notification_channels.id", ondelete="CASCADE"), index=True
    )
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
