"""System endpoints for health checks and system information."""

from datetime import datetime
from fastapi import APIRouter

from ..core.config import settings

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health", summary="Service health check")
async def health_check() -> dict:
    """Check the health and status of the API."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": settings.APP_VERSION,
        "app_name": settings.APP_NAME
    }


@router.get("/info", summary="System information")
async def system_info() -> dict:
    """Get system information and configuration."""
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "debug": settings.DEBUG,
        "database_url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "configured",
        "redis_host": settings.REDIS_HOST,
        "clickhouse_host": settings.CLICKHOUSE_HOST
    } 