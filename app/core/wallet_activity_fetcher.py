"""Wallet Activity Fetcher - Fetches and stores wallet activities from blockchain explorers."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from .database import SessionLocal
from .blockchain_explorer_service import blockchain_explorer_service
from ..models import WalletConnection, WalletActivity
from ..crud.wallets import wallet_activity_crud
from ..schemas import WalletActivityCreate

logger = logging.getLogger(__name__)


class WalletActivityFetcher:
    """Service for fetching and storing wallet activities."""
    
    def __init__(self):
        self.blockchain_service = blockchain_explorer_service
        self.batch_size = 100  # Process transactions in batches
        self.max_retries = 3
    
    async def fetch_wallet_activities(
        self, 
        wallet_connection_id: str,
        days_back: int = 30,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch and store wallet activities for a specific wallet connection.
        
        Args:
            wallet_connection_id: The wallet connection ID
            days_back: Number of days to look back for transactions
            force_refresh: Whether to force refresh even if recent data exists
            
        Returns:
            Dictionary with fetch results
        """
        db = SessionLocal()
        try:
            # Get wallet connection
            wallet = db.query(WalletConnection).filter(
                WalletConnection.id == wallet_connection_id
            ).first()
            
            if not wallet:
                return {
                    'success': False,
                    'error': 'Wallet connection not found',
                    'transactions_fetched': 0
                }
            
            # Check if we need to fetch (avoid duplicate fetches)
            if not force_refresh:
                recent_activity = db.query(WalletActivity).filter(
                    and_(
                        WalletActivity.wallet_connection_id == wallet_connection_id,
                        WalletActivity.timestamp >= datetime.now(timezone.utc) - timedelta(hours=1)
                    )
                ).first()
                
                if recent_activity:
                    logger.info(f"Recent activity found for wallet {wallet.wallet_address}, skipping fetch")
                    return {
                        'success': True,
                        'message': 'Recent activity found, skipping fetch',
                        'transactions_fetched': 0
                    }
            
            # Calculate date range (use a longer period to catch more transactions)
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=max(days_back, 30))  # At least 30 days
            
            logger.info(f"Fetching activities for wallet {wallet.wallet_address} from {start_date} to {end_date}")
            
            # Fetch transactions from blockchain explorer
            transactions = await self.blockchain_service.fetch_wallet_transactions(
                wallet_address=wallet.wallet_address,
                network=wallet.network,
                limit=1000  # Adjust based on API limits
            )
            
            if not transactions:
                return {
                    'success': True,
                    'message': 'No transactions found',
                    'transactions_fetched': 0
                }
            
            # Filter transactions by date range
            filtered_transactions = []
            for tx in transactions:
                tx_timestamp = tx.get('timestamp')
                if tx_timestamp:
                    # Ensure timestamp is timezone-aware
                    if tx_timestamp.tzinfo is None:
                        tx_timestamp = tx_timestamp.replace(tzinfo=timezone.utc)
                    if start_date <= tx_timestamp <= end_date:
                        filtered_transactions.append(tx)
            
            logger.info(f"Found {len(filtered_transactions)} transactions in date range")
            
            # Store transactions in database
            stored_count = await self._store_transactions(
                db, wallet_connection_id, filtered_transactions
            )
            
            return {
                'success': True,
                'transactions_fetched': len(filtered_transactions),
                'transactions_stored': stored_count,
                'wallet_address': wallet.wallet_address,
                'network': wallet.network
            }
            
        except Exception as e:
            logger.error(f"Error fetching wallet activities: {e}")
            return {
                'success': False,
                'error': str(e),
                'transactions_fetched': 0
            }
        finally:
            db.close()
    
    async def _store_transactions(
        self, 
        db: Session, 
        wallet_connection_id: str, 
        transactions: List[Dict[str, Any]]
    ) -> int:
        """Store transactions in the database."""
        stored_count = 0
        
        for tx in transactions:
            try:
                # Check if transaction already exists
                existing = db.query(WalletActivity).filter(
                    WalletActivity.transaction_hash == tx.get('transaction_hash', '')
                ).first()
                
                if existing:
                    continue  # Skip duplicate transactions
                
                # Create wallet activity record
                activity_data = WalletActivityCreate(
                    wallet_connection_id=wallet_connection_id,
                    activity_type=tx.get('transaction_type', 'transfer'),  # Use transaction_type as activity_type
                    transaction_hash=tx.get('transaction_hash', ''),
                    block_number=tx.get('block_number'),
                    transaction_type=tx.get('transaction_type', 'transfer'),
                    from_address=tx.get('from_address', ''),
                    to_address=tx.get('to_address', ''),
                    token_address=tx.get('token_address'),
                    token_symbol=tx.get('token_symbol'),
                    token_name=tx.get('token_name'),
                    amount=tx.get('value', 0),
                    amount_usd=tx.get('amount_usd'),  # Would need price data
                    gas_used=tx.get('gas_used'),
                    gas_price=tx.get('gas_price'),
                    gas_fee_usd=tx.get('gas_fee_usd'),  # Would need price data
                    network=tx.get('network', 'ethereum'),
                    status=tx.get('status', 'confirmed'),
                    timestamp=tx.get('timestamp', datetime.now(timezone.utc)),
                    transaction_metadata=tx.get('transaction_metadata', {})
                )
                
                # Store in database
                wallet_activity_crud.create_wallet_activity(db, activity_data)
                stored_count += 1
                
            except Exception as e:
                logger.error(f"Error storing transaction {tx.get('transaction_hash', 'unknown')}: {e}")
                continue
        
        db.commit()
        return stored_count
    
    async def fetch_all_wallet_activities(
        self, 
        company_id: Optional[str] = None,
        days_back: int = 30,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch activities for all wallet connections.
        
        Args:
            company_id: Optional company ID to filter wallets
            days_back: Number of days to look back
            force_refresh: Whether to force refresh
            
        Returns:
            Dictionary with overall results
        """
        db = SessionLocal()
        try:
            # Get all wallet connections
            query = db.query(WalletConnection)
            if company_id:
                query = query.filter(WalletConnection.company_id == company_id)
            
            wallets = query.all()
            
            if not wallets:
                return {
                    'success': True,
                    'message': 'No wallet connections found',
                    'wallets_processed': 0,
                    'total_transactions': 0
                }
            
            logger.info(f"Processing {len(wallets)} wallet connections")
            
            total_transactions = 0
            successful_wallets = 0
            failed_wallets = 0
            
            # Process each wallet
            for wallet in wallets:
                try:
                    result = await self.fetch_wallet_activities(
                        str(wallet.id), days_back, force_refresh
                    )
                    
                    if result['success']:
                        successful_wallets += 1
                        total_transactions += result.get('transactions_fetched', 0)
                    else:
                        failed_wallets += 1
                        logger.warning(f"Failed to fetch activities for wallet {wallet.wallet_address}: {result.get('error', 'Unknown error')}")
                    
                    # Add delay between requests to respect rate limits
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing wallet {wallet.wallet_address}: {e}")
                    failed_wallets += 1
                    continue
            
            return {
                'success': True,
                'wallets_processed': len(wallets),
                'successful_wallets': successful_wallets,
                'failed_wallets': failed_wallets,
                'total_transactions': total_transactions
            }
            
        except Exception as e:
            logger.error(f"Error in fetch_all_wallet_activities: {e}")
            return {
                'success': False,
                'error': str(e),
                'wallets_processed': 0,
                'total_transactions': 0
            }
        finally:
            db.close()
    
    async def sync_wallet_activities(self, wallet_connection_id: str) -> Dict[str, Any]:
        """Sync recent activities for a specific wallet (last 24 hours)."""
        return await self.fetch_wallet_activities(
            wallet_connection_id, 
            days_back=1, 
            force_refresh=True
        )
    
    async def get_wallet_activity_summary(self, wallet_connection_id: str) -> Dict[str, Any]:
        """Get a summary of wallet activities."""
        db = SessionLocal()
        try:
            # Get recent activities
            recent_activities = db.query(WalletActivity).filter(
                WalletActivity.wallet_connection_id == wallet_connection_id
            ).order_by(desc(WalletActivity.timestamp)).limit(10).all()
            
            # Get activity counts by type
            activity_counts = db.query(
                WalletActivity.transaction_type,
                db.func.count(WalletActivity.id)
            ).filter(
                WalletActivity.wallet_connection_id == wallet_connection_id
            ).group_by(WalletActivity.transaction_type).all()
            
            # Get total transaction count
            total_transactions = db.query(WalletActivity).filter(
                WalletActivity.wallet_connection_id == wallet_connection_id
            ).count()
            
            return {
                'total_transactions': total_transactions,
                'recent_activities': [
                    {
                        'transaction_hash': activity.transaction_hash,
                        'transaction_type': activity.transaction_type,
                        'amount': float(activity.amount) if activity.amount else 0,
                        'timestamp': activity.timestamp.isoformat(),
                        'status': activity.status
                    }
                    for activity in recent_activities
                ],
                'activity_breakdown': {
                    tx_type: count for tx_type, count in activity_counts
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting wallet activity summary: {e}")
            return {'error': str(e)}
        finally:
            db.close()


# Create global instance
wallet_activity_fetcher = WalletActivityFetcher()
