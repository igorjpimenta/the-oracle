"""
Health check endpoints.
"""

from fastapi import APIRouter
from datetime import datetime

from .. import __version__
from ..models.schemas import HealthResponse

router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        version=__version__,
    )
