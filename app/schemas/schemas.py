"""
Pydantic schemas for API request/response validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ==================== Enums ====================

class TestRunStatus(str, Enum):
    """Test run status values."""
    PENDING = "Pending"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


# ==================== Product Schemas ====================

class ProductBase(BaseModel):
    """Base product schema."""
    name: str
    description: Optional[str] = None
    openproject_id: Optional[str] = None


class ProductCreate(ProductBase):
    """Schema for creating a product."""
    pass


class ProductResponse(ProductBase):
    """Schema for product response."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Runner Schemas ====================

class RunnerRegister(BaseModel):
    """Schema for runner registration.

    M2: Enforce strict length limits and character constraints on username/password.
    """
    # M2: tighter max_length and explicit pattern to avoid control chars / injection
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_\-]+$")
    password: str = Field(..., min_length=12, max_length=128)
    socket_port: int = Field(default=53035, ge=1024, le=65535)
    location: Optional[str] = Field(default=None, max_length=255)


class RunnerResponse(BaseModel):
    """Schema for runner response."""
    id: int
    account: str
    socket_port: int
    location: Optional[str]
    is_active: bool
    last_heartbeat: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class RunnerToken(BaseModel):
    """Schema for runner token response."""
    account: str
    token: str
    message: str = "Runner registered successfully"


class RunnerHeartbeat(BaseModel):
    """Schema for runner heartbeat."""
    # M2: limit account field length to match DB constraint
    runner_account: str = Field(..., min_length=3, max_length=50)


# ==================== Test Run Schemas ====================

class TestRunCreate(BaseModel):
    """Schema for creating a test run."""
    test_case_list: str
    test_suite_name: str
    url_test_software: Optional[str] = None
    ref_test_software: str = "main"
    product_composition_id: Optional[int] = None
    status: TestRunStatus = TestRunStatus.RUNNING
    pipeline_software_under_test: bool = False
    runner_account: Optional[str] = None


class TestRunUpdate(BaseModel):
    """Schema for updating a test run."""
    status: Optional[TestRunStatus] = None
    total_tests: Optional[int] = None
    passed_tests: Optional[int] = None
    failed_tests: Optional[int] = None
    skipped_tests: Optional[int] = None
    duration_seconds: Optional[float] = None
    completed_at: Optional[datetime] = None
    results: Optional[List[Dict[str, Any]]] = None


class TestRunResponse(BaseModel):
    """Schema for test run response."""
    id: int
    name: str
    test_case_list: str
    status: str
    url_test_software: Optional[str]
    ref_test_software: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    duration_seconds: Optional[float]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    product_id: Optional[int]
    runner_id: Optional[int]

    class Config:
        from_attributes = True


class TestRunList(BaseModel):
    """Schema for test run list response."""
    runs: List[TestRunResponse]
    total: int
    limit: int
    offset: int


# ==================== Test Result Schemas ====================

class TestResultCreate(BaseModel):
    """Schema for creating a test result."""
    test_class: str
    test_method: str
    passed: bool
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    traceback: Optional[str] = None
    assertions: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    work_package_id: Optional[int] = None


class TestResultResponse(BaseModel):
    """Schema for test result response."""
    id: int
    test_class: str
    test_method: str
    passed: bool
    duration_seconds: float
    error_message: Optional[str]
    traceback: Optional[str]
    assertions: Optional[List[Dict[str, Any]]]
    metadata: Optional[Dict[str, Any]]
    work_package_id: Optional[int]
    created_at: datetime
    test_run_id: int

    class Config:
        from_attributes = True


class ResultsUpload(BaseModel):
    """Schema for uploading multiple results."""
    results: List[TestResultCreate]
    test_run_id: Optional[int] = None


# ==================== Artifact Schemas ====================

class ArtifactResponse(BaseModel):
    """Schema for artifact response."""
    id: int
    filename: str
    original_filename: str
    content_type: str
    size_bytes: int
    test_case: Optional[str]
    created_at: datetime
    test_run_id: Optional[int]

    class Config:
        from_attributes = True


# ==================== Health Schemas ====================

class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str = "healthy"
    version: str
    database: str = "connected"


class VersionResponse(BaseModel):
    """Schema for version response."""
    version: str
    api_version: str = "v1"
