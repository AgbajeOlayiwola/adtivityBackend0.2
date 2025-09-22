"""Startup tasks for the application."""

import asyncio
import logging
from contextlib import asynccontextmanager

from .background_tasks import background_task_service
from .wallet_sync_service import wallet_sync_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def startup_tasks():
    """Manage startup and shutdown tasks."""
    # Startup
    logger.info("🚀 Starting background services...")
    
    # Start Twitter auto-sync in background
    twitter_sync_task = asyncio.create_task(background_task_service.start_auto_sync())
    
    # Start wallet auto-sync in background
    wallet_sync_task = asyncio.create_task(wallet_sync_service.start_auto_sync())
    
    try:
        yield
    finally:
        # Shutdown
        logger.info("🛑 Shutting down background services...")
        
        # Stop auto-sync services
        background_task_service.stop_auto_sync()
        wallet_sync_service.stop_auto_sync()
        
        # Cancel the sync tasks
        twitter_sync_task.cancel()
        wallet_sync_task.cancel()
        
        try:
            await twitter_sync_task
        except asyncio.CancelledError:
            logger.info("✅ Twitter sync task cancelled")
            
        try:
            await wallet_sync_task
        except asyncio.CancelledError:
            logger.info("✅ Wallet sync task cancelled")
        
        logger.info("✅ Background services stopped")
