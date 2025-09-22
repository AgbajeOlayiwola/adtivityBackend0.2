"""Wallet Sync Service - Background service for syncing wallet activities."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from .database import SessionLocal
from .wallet_activity_fetcher import wallet_activity_fetcher
from ..models import WalletConnection

logger = logging.getLogger(__name__)


class WalletSyncService:
    """Background service for syncing wallet activities."""
    
    def __init__(self):
        self.is_running = False
        self.sync_interval = 3600  # 1 hour in seconds
        self.batch_size = 10  # Process wallets in batches
        self.max_concurrent = 3  # Maximum concurrent wallet fetches
    
    async def start_auto_sync(self):
        """Start automatic wallet activity syncing."""
        if self.is_running:
            logger.warning("Wallet sync is already running")
            return
        
        self.is_running = True
        logger.info("🚀 Starting automatic wallet activity sync service")
        
        while self.is_running:
            try:
                await self._sync_all_wallets()
                logger.info(f"✅ Wallet sync completed. Next sync in {self.sync_interval} seconds")
                await asyncio.sleep(self.sync_interval)
            except Exception as e:
                logger.error(f"❌ Error in wallet sync: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    def stop_auto_sync(self):
        """Stop automatic wallet syncing."""
        self.is_running = False
        logger.info("🛑 Stopping automatic wallet sync service")
    
    async def _sync_all_wallets(self):
        """Sync all wallet connections in the database."""
        db = SessionLocal()
        try:
            # Get all verified wallet connections
            wallets = db.query(WalletConnection).filter(
                WalletConnection.is_verified == True
            ).all()
            
            if not wallets:
                logger.info("No verified wallet connections found")
                return
            
            logger.info(f"Found {len(wallets)} verified wallet connections to sync")
            
            # Process wallets in batches
            for i in range(0, len(wallets), self.batch_size):
                batch = wallets[i:i + self.batch_size]
                await self._sync_wallet_batch(batch)
                
                # Add delay between batches to respect rate limits
                if i + self.batch_size < len(wallets):
                    await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Error in _sync_all_wallets: {e}")
        finally:
            db.close()
    
    async def _sync_wallet_batch(self, wallets: List[WalletConnection]):
        """Sync a batch of wallets concurrently."""
        tasks = []
        
        for wallet in wallets:
            task = self._sync_single_wallet(wallet)
            tasks.append(task)
        
        # Run tasks with concurrency limit
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def limited_sync(wallet):
            async with semaphore:
                return await self._sync_single_wallet(wallet)
        
        # Execute all tasks
        results = await asyncio.gather(
            *[limited_sync(wallet) for wallet in wallets],
            return_exceptions=True
        )
        
        # Log results
        successful = sum(1 for result in results if isinstance(result, dict) and result.get('success'))
        failed = len(results) - successful
        
        logger.info(f"Batch sync completed: {successful} successful, {failed} failed")
    
    async def _sync_single_wallet(self, wallet: WalletConnection) -> Dict[str, Any]:
        """Sync activities for a single wallet."""
        try:
            logger.info(f"Syncing wallet {wallet.wallet_address} ({wallet.network})")
            
            result = await wallet_activity_fetcher.fetch_wallet_activities(
                str(wallet.id),
                days_back=7,  # Sync last 7 days
                force_refresh=False
            )
            
            if result['success']:
                transactions_fetched = result.get('transactions_fetched', 0)
                if transactions_fetched > 0:
                    logger.info(f"✅ Synced {transactions_fetched} transactions for {wallet.wallet_address}")
                else:
                    logger.info(f"ℹ️ No new transactions for {wallet.wallet_address}")
            else:
                logger.warning(f"❌ Failed to sync {wallet.wallet_address}: {result.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error syncing wallet {wallet.wallet_address}: {e}")
            return {
                'success': False,
                'error': str(e),
                'transactions_fetched': 0
            }
    
    async def sync_company_wallets(self, company_id: str) -> Dict[str, Any]:
        """Sync all wallets for a specific company."""
        try:
            logger.info(f"Syncing wallets for company {company_id}")
            
            result = await wallet_activity_fetcher.fetch_all_wallet_activities(
                company_id=company_id,
                days_back=30,
                force_refresh=True
            )
            
            logger.info(f"Company sync completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error syncing company wallets: {e}")
            return {
                'success': False,
                'error': str(e),
                'wallets_processed': 0
            }
    
    async def sync_wallet_on_connect(self, wallet_connection_id: str) -> Dict[str, Any]:
        """Sync wallet activities immediately after connection."""
        try:
            logger.info(f"Initial sync for new wallet connection {wallet_connection_id}")
            
            result = await wallet_activity_fetcher.fetch_wallet_activities(
                wallet_connection_id,
                days_back=90,  # Fetch more history for new connections
                force_refresh=True
            )
            
            if result['success']:
                transactions = result.get('transactions_fetched', 0)
                logger.info(f"✅ Initial sync completed: {transactions} transactions fetched")
            else:
                logger.warning(f"❌ Initial sync failed: {result.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in initial wallet sync: {e}")
            return {
                'success': False,
                'error': str(e),
                'transactions_fetched': 0
            }
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """Get the current sync service status."""
        db = SessionLocal()
        try:
            # Get wallet connection counts
            total_wallets = db.query(WalletConnection).count()
            verified_wallets = db.query(WalletConnection).filter(
                WalletConnection.is_verified == True
            ).count()
            
            # Get recent sync activity
            from ..models import WalletActivity
            recent_activities = db.query(WalletActivity).filter(
                WalletActivity.timestamp >= datetime.utcnow() - timedelta(hours=24)
            ).count()
            
            return {
                'service_running': self.is_running,
                'sync_interval': self.sync_interval,
                'total_wallets': total_wallets,
                'verified_wallets': verified_wallets,
                'recent_activities_24h': recent_activities,
                'last_sync': datetime.utcnow().isoformat() if self.is_running else None
            }
            
        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return {
                'service_running': self.is_running,
                'error': str(e)
            }
        finally:
            db.close()


# Create global instance
wallet_sync_service = WalletSyncService()
