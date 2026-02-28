"""
Health check endpoints.
"""

from fastapi import APIRouter

from app.schemas import HealthResponse, VersionResponse
from app import __version__

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns the health status of the API and its dependencies.
    """
    return HealthResponse(
        status="healthy",
        version=__version__,
        database="connected",
    )


@router.get("/version", response_model=VersionResponse)
async def get_version():
    """
    Get API version information.
    """
    return VersionResponse(
        version=__version__,
        api_version="v1",
    )
