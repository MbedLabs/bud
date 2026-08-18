"""
Health check endpoints.

Two distinct probes:

* ``/api/health`` — *liveness*. Only reports that the process is up. It never
  touches the database, so it must not be relied on to infer dependency health.
* ``/api/ready`` — *readiness*. Verifies the database is reachable (``SELECT 1``)
  and returns HTTP 503 when it is not, so load balancers and orchestrators can
  stop routing to an instance that cannot serve requests.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app import __version__
from app.db.database import engine
from app.schemas import HealthResponse, ReadinessResponse, VersionResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Liveness probe.

    Reports only that the API process is serving. It deliberately does not query
    the database — use ``/api/ready`` for a real dependency check.
    """
    return HealthResponse(status="healthy", version=__version__)


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check():
    """
    Readiness probe.

    Confirms the database is actually reachable with ``SELECT 1``. Returns HTTP
    503 when the dependency is unavailable.
    """
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
