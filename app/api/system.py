"""System endpoints for health checks and system information."""

from datetime import datetime, timezone
from fastapi import APIRouter

from ..core.config import settings
from ..core.event_cleanup_service import purge_localhost_events

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health", summary="Service health check")
async def health_check() -> dict:
    """Check the health and status of the API."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc),
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
        "clickhouse_host": settings.CLICKHOUSE_HOST,
        "timestamp": datetime.now(timezone.utc)
    }


@router.post("/purge-localhost-events", summary="Manually purge localhost events older than 24h")
async def purge_localhost() -> dict:
    """Trigger a one-off purge of localhost-originated events older than 24 hours."""
    events_deleted, web3_deleted, raw_deleted = purge_localhost_events()
    return {
        "status": "completed",
        "events_deleted": events_deleted,
        "web3_events_deleted": web3_deleted,
        "raw_events_deleted": raw_deleted,
        "cutoff_hours": 24,
        "timestamp": datetime.now(timezone.utc)
    }
