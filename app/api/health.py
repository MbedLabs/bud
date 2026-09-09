"""Health check endpoints."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app import __version__
from app.db.database import engine
from app.schemas import HealthResponse, ReadinessResponse, VersionResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Liveness probe."""
    return HealthResponse(status="healthy", version=__version__)


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check():
    """Readiness probe."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - failure path exercised in CI e2e
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "database": "unavailable"},
        ) from exc

    return ReadinessResponse(status="ready", version=__version__, database="connected")


@router.get("/version", response_model=VersionResponse)
async def get_version():
    """
    Get API version information.
    """
    return VersionResponse(
        version=__version__,
        api_version="v1",
    )
