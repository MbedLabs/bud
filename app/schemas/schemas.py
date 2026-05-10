"""
Pydantic schemas for API request/response validation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional  # noqa: F401

from pydantic import BaseModel, Field, field_serializer, field_validator

# ==================== Enums ====================


class TestRunStatus(str, Enum):
    """Test run status values."""

    PENDING = "Pending"
    RUNNING = "Running"
    COMPLETED = "Completed"
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

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, dt: datetime, _info):
        return f"{dt.isoformat()}Z"

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

    @field_serializer("last_heartbeat", "created_at")
    def serialize_dt(self, dt: Optional[datetime], _info):
        return f"{dt.isoformat()}Z" if dt else None

    class Config:
        from_attributes = True


class RunnerStatusEntry(RunnerResponse):
    """Schema for runner status entry with dynamic online status."""

    is_online: bool


class RunnerStatusList(BaseModel):
    """Schema for runner status list response."""

    runners: List[RunnerStatusEntry]


class RunnerToken(BaseModel):
    """Schema for runner token response."""

    account: str
    token: str
    message: str = "Runner registered successfully"


class RunnerHeartbeat(BaseModel):
    """Schema for runner heartbeat."""

    # M2: limit account field length to match DB constraint
    runner_account: str = Field(..., min_length=3, max_length=50)
    location: Optional[str] = Field(default=None, max_length=255)


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
    product_id: Optional[int] = None


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
    runner_account: Optional[str] = None

    @field_serializer("created_at", "started_at", "completed_at")
    def serialize_dt(self, dt: Optional[datetime], _info):
        return f"{dt.isoformat()}Z" if dt else None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_runner(cls, test_run: Any) -> "TestRunResponse":
        """Build a response that also exposes the Bud runner's account name.

        Frontend ("Test Station" filter and detail page) wants a human-readable
        station identifier; ``runner_id`` alone forces a second lookup per
        row. Accessing ``test_run.runner`` requires the relationship to be
        loaded (selectinload) or the session to still be attached.
        """
        data = {c.name: getattr(test_run, c.name) for c in test_run.__table__.columns}
        runner = getattr(test_run, "runner", None)
        data["runner_account"] = runner.account if runner else None
        return cls.model_validate(data)


class TestRunEventResponse(BaseModel):
    """System-reported execution/integration step for a test run."""

    id: int
    test_run_id: int
    sequence: int
    stage: str
    status: str
    title: str
    message: Optional[str]
    event_metadata: Optional[Dict[str, Any]]
    created_at: datetime

    @field_serializer("created_at")
    def serialize_dt(self, dt: datetime, _info):
        return f"{dt.isoformat()}Z"

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
    test_metadata: Optional[Dict[str, Any]]
    work_package_id: Optional[int]
    created_at: datetime
    test_run_id: Optional[int] = None

    @field_serializer("created_at")
    def serialize_dt(self, dt: datetime, _info):
        return f"{dt.isoformat()}Z"

    class Config:
        from_attributes = True


class ResultsUpload(BaseModel):
    """Schema for uploading multiple results."""

    results: List[TestResultCreate]
    test_run_id: Optional[int] = None
    product_id: Optional[int] = None
    runner_account: Optional[str] = None
    test_suite_name: Optional[str] = None


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

    @field_serializer("created_at")
    def serialize_dt(self, dt: datetime, _info):
        return f"{dt.isoformat()}Z"

    class Config:
        from_attributes = True


# ==================== TestStation Schemas ====================


class TestStationRegister(BaseModel):
    """Schema for teststation registration."""

    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_\-]+$")
    password: str = Field(..., min_length=12, max_length=128)
    socket_port: int = Field(default=53035, ge=1024, le=65535)
    location: Optional[str] = Field(default=None, max_length=255)


class TestStationResponse(BaseModel):
    """Schema for teststation response."""

    id: int
    account: str
    socket_port: int
    location: Optional[str]
    is_active: bool
    last_heartbeat: Optional[datetime]
    created_at: datetime

    @field_serializer("last_heartbeat", "created_at")
    def serialize_dt(self, dt: Optional[datetime], _info):
        return f"{dt.isoformat()}Z" if dt else None

    class Config:
        from_attributes = True


class TestStationStatusEntry(TestStationResponse):
    """Schema for teststation status entry with dynamic online status."""

    is_online: bool


class TestStationStatusList(BaseModel):
    """Schema for teststation status list response."""

    teststations: List[TestStationStatusEntry]


class TestStationToken(BaseModel):
    """Schema for teststation token response."""

    account: str
    token: str
    message: str = "TestStation registered successfully"


class TestStationHeartbeat(BaseModel):
    """Schema for teststation heartbeat."""

    teststation_account: str = Field(..., min_length=3, max_length=50)


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


# ==================== Settings Schemas ====================


class SystemSettingBase(BaseModel):
    """Base schema for system settings."""

    key: str
    value: str
    description: Optional[str] = None


class SystemSettingUpdate(BaseModel):
    """Schema for updating a system setting."""

    value: str
    description: Optional[str] = None


class SystemSettingResponse(SystemSettingBase):
    """Schema for system setting response."""

    updated_at: datetime

    @field_serializer("updated_at")
    def serialize_dt(self, dt: datetime, _info):
        return f"{dt.isoformat()}Z"

    class Config:
        from_attributes = True


class ALMIntegrationSettings(BaseModel):
    """Schema for PLM integration settings (Bloom)."""

    bloom_url: str
    bloom_token: str
