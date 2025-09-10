"""Startup tasks for the application."""

import asyncio
import logging
from contextlib import asynccontextmanager

from .background_tasks import background_task_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def startup_tasks():
    """Manage startup and shutdown tasks."""
    # Startup
    logger.info("🚀 Starting background services...")
    
    # Start Twitter auto-sync in background
    sync_task = asyncio.create_task(background_task_service.start_auto_sync())
    
    try:
        yield
    finally:
        # Shutdown
        logger.info("🛑 Shutting down background services...")
        
        # Stop auto-sync
        background_task_service.stop_auto_sync()
        
        # Cancel the sync task
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            logger.info("✅ Background sync task cancelled")
        
        logger.info("✅ Background services stopped")
