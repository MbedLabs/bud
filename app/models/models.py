"""
Database models for the bud test platform.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Product(Base):
    """Product/project being tested."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    test_runs: Mapped[List["TestRun"]] = relationship(back_populates="product")
    results: Mapped[List["TestResult"]] = relationship(
        "TestResult", backref="product_ref"
    )  # backref to avoid collision with existing attributes


class Runner(Base):
    """Test runner (test bench) registration."""

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

    # Relationships
    test_runs: Mapped[List["TestRun"]] = relationship(back_populates="runner")


class TestRun(Base):
    """A test run execution."""

    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    test_case_list: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), default="Pending")

    # Software under test
    url_test_software: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ref_test_software: Mapped[str] = mapped_column(String(100), default="main")

    # Statistics
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    passed_tests: Mapped[int] = mapped_column(Integer, default=0)
    failed_tests: Mapped[int] = mapped_column(Integer, default=0)
    skipped_tests: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Foreign keys
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    runner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("runners.id"), nullable=True)

    # Relationships
    product: Mapped[Optional["Product"]] = relationship(back_populates="test_runs")
    runner: Mapped[Optional["Runner"]] = relationship(back_populates="test_runs")
    results: Mapped[List["TestResult"]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )
    artifacts: Mapped[List["Artifact"]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )


class TestResult(Base):
    """Result of a single test case execution."""

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

    # OpenProject integration
    work_package_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Foreign keys (optional: detached uploads before a TestRun exists)
    test_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("test_runs.id"), nullable=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)

    # Relationships
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

    test_case: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Foreign key
    test_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("test_runs.id"), nullable=True)

    # Relationships
    test_run: Mapped[Optional["TestRun"]] = relationship(back_populates="artifacts")
