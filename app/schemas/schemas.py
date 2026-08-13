"""
Pydantic schemas for API request/response validation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional  # noqa: F401

from pydantic import BaseModel, Field, field_serializer

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


class CurrentRunSummary(BaseModel):
    """Lightweight view of a test run currently executing on a runner."""

    id: int
    name: str


class RunnerStatusEntry(RunnerResponse):
    """Schema for runner status entry with dynamic online status."""

    is_online: bool
    current_run: Optional[CurrentRunSummary] = None


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
    url_software_under_test: Optional[str] = None
    ref_software_under_test: Optional[str] = None
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
    url_software_under_test: Optional[str]
    ref_software_under_test: Optional[str]
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    duration_seconds: Optional[float]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    claim_acknowledged_at: Optional[datetime] = None
    runner_exit_code: Optional[int] = None
    runner_error: Optional[str] = None
    product_id: Optional[int]
    runner_id: Optional[int]
    runner_account: Optional[str] = None
    # Present only on a custom run: the test cases it was built from, as the
    # importable paths the runner's loader takes.
    selected_tests: Optional[List[str]] = None

    @field_serializer("created_at", "started_at", "completed_at", "claim_acknowledged_at")
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


class TestRunStats(BaseModel):
    """Aggregate run and test-case counters behind the dashboard tiles."""

    total_runs: int
    passed_runs: int
    failed_runs: int
    in_progress_runs: int
    # Share of decided (passed or failed) runs that passed; pending runs are excluded
    # so a queued backlog cannot drag the reported rate down.
    run_pass_rate: float
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    test_pass_rate: float


class TestRunFilterOptions(BaseModel):
    """Values offered by the dashboard filter controls."""

    suites: List[str]
    runner_accounts: List[str]


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


class TestResultListItem(BaseModel):
    """A result as the run detail lists it: everything but the traceback.

    The run detail draws its per-assertion table from the `assertions` blob,
    and the traceback it shows for a failure comes from inside that blob -
    `assertion.traceback`. The result's own `traceback` column is a separate
    full stack trace per failed method, and no screen renders it, so listing a
    run read a few kilobytes per failure out of the database and threw them
    away.

    Deliberately not a subclass of TestResultResponse: excluding a field from
    the response would still leave the column being selected and hydrated,
    which is where the cost is. The listing query selects these columns and no
    others. The traceback is still on `GET /api/results/detail/{id}`, which is
    where a single result is fetched in full.
    """

    id: int
    test_class: str
    test_method: str
    passed: bool
    duration_seconds: float
    error_message: Optional[str]
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
    url_test_software: Optional[str] = None
    ref_test_software: Optional[str] = None
    url_software_under_test: Optional[str] = None
    ref_software_under_test: Optional[str] = None


# ==================== Artifact Schemas ====================


class CatalogEntryResponse(BaseModel):
    """One test case Bud has a record of, and where it has run."""

    test_path: str
    test_class: str
    suite: str
    runner_accounts: List[str]
    method_count: int
    last_run_at: Optional[datetime] = None
    last_passed: Optional[bool] = None
    last_run_id: Optional[int] = None

    @field_serializer("last_run_at")
    def serialize_dt(self, dt: Optional[datetime], _info):
        return f"{dt.isoformat()}Z" if dt else None

    class Config:
        from_attributes = True


class TestCatalogResponse(BaseModel):
    entries: List[CatalogEntryResponse]
    total: int


class CustomRunRequest(BaseModel):
    """A selection of test cases to queue."""

    test_paths: List[str] = Field(..., min_length=1, max_length=200)
    name: Optional[str] = Field(default=None, max_length=255)
    runner_account: Optional[str] = Field(
        default=None,
        description="Pin every test to this Test Station instead of the one that last ran it.",
    )


class UnassignedTest(BaseModel):
    test_path: str
    reason: str


class CustomRunResponse(BaseModel):
    """What was queued, and what could not be.

    A selection spanning two benches becomes two runs, so this is a list even
    when the reader picked what looked like one thing.
    """

    runs: List[TestRunResponse]
    unassigned: List[UnassignedTest]


class ClaimedRunResponse(BaseModel):
    """The run a Test Station has just taken, and what to execute.

    `selected_tests` is set for a custom run and is the authoritative list.
    `test_case_list` is the module path an ordinary run names, kept so a station
    that claims a queued ordinary run resolves it the way it always has.
    """

    claim_id: str
    run: TestRunResponse
    selected_tests: Optional[List[str]] = None


class ClaimedRunCompletion(BaseModel):
    """The terminal process answer for one claimed execution."""

    exit_code: int
    error: Optional[str] = Field(default=None, max_length=4000)


class BloomPublishRequest(BaseModel):
    """Which Bloom project the run's report belongs to."""

    project_prefix: str = Field(..., min_length=1, max_length=20)


class BloomPublishResponse(BaseModel):
    document_id: Optional[int] = None
    doc_id: Optional[str] = None
    created: bool = False
    published_files: List[str] = Field(default_factory=list)


class ArtifactResponse(BaseModel):
    """Schema for artifact response."""

    id: int
    filename: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: Optional[str] = None
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
    """Schema for the liveness probe response."""

    status: str = "healthy"
    version: str
    # Liveness never inspects the database, so it must not claim a connection it
    # has not verified. The real dependency check lives at /api/ready.
    database: str = "not_checked"


class ReadinessResponse(BaseModel):
    """Schema for the readiness probe response (database verified via SELECT 1)."""

    status: str = "ready"
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
    has_bloom_token: bool = False
    bloom_token_prefix: Optional[str] = None
    bloom_token_rotated_at: Optional[datetime] = None


class ALMIntegrationSettingsUpdate(BaseModel):
    """One-way update: secrets are accepted but never returned."""

    bloom_url: str
    bloom_token: Optional[str] = None
    clear_bloom_token: bool = False
