"""CRUD operations for wallet connections and activities."""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from ..models import WalletConnection, WalletActivity, ClientCompany
from ..schemas import (
    WalletConnectionCreate, 
    WalletConnectionUpdate,
    WalletActivityCreate
)


class WalletCRUD:
    """CRUD operations for wallet connections."""
    
    def create_wallet_connection(
        self, 
        db: Session, 
        wallet_data: WalletConnectionCreate
    ) -> WalletConnection:
        """Create a new wallet connection."""
        db_wallet = WalletConnection(
            company_id=wallet_data.company_id,
            wallet_address=wallet_data.wallet_address,  # Store in original case
            wallet_type=wallet_data.wallet_type,
            network=wallet_data.network,
            wallet_name=wallet_data.wallet_name,
            is_verified=bool(wallet_data.verification_signature)
        )
        
        if wallet_data.verification_signature:
            db_wallet.verification_method = "signature"
            db_wallet.verification_timestamp = datetime.utcnow()
        
        db.add(db_wallet)
        db.commit()
        db.refresh(db_wallet)
        return db_wallet
    
    def get_wallet_connection(
        self, 
        db: Session, 
        wallet_id: uuid.UUID
    ) -> Optional[WalletConnection]:
        """Get a wallet connection by ID."""
        return db.query(WalletConnection).filter(
            WalletConnection.id == wallet_id
        ).first()
    
    def get_wallet_connection_by_address(
        self, 
        db: Session, 
        company_id: uuid.UUID,
        wallet_address: str
    ) -> Optional[WalletConnection]:
        """Get a wallet connection by company and address."""
        return db.query(WalletConnection).filter(
            and_(
                WalletConnection.company_id == company_id,
                WalletConnection.wallet_address == wallet_address
            )
        ).first()
    
    def get_company_wallets(
        self, 
        db: Session, 
        company_id: uuid.UUID,
        active_only: bool = True
    ) -> List[WalletConnection]:
        """Get all wallet connections for a company."""
        query = db.query(WalletConnection).filter(
            WalletConnection.company_id == company_id
        )
        
        if active_only:
            query = query.filter(WalletConnection.is_active == True)
        
        return query.order_by(desc(WalletConnection.created_at)).all()
    
    def update_wallet_connection(
        self, 
        db: Session, 
        wallet_id: uuid.UUID,
        wallet_data: WalletConnectionUpdate
    ) -> Optional[WalletConnection]:
        """Update a wallet connection."""
        db_wallet = self.get_wallet_connection(db, wallet_id)
        if not db_wallet:
            return None
        
        update_data = wallet_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_wallet, field, value)
        
        db.commit()
        db.refresh(db_wallet)
        return db_wallet
    
    def delete_wallet_connection(
        self, 
        db: Session, 
        wallet_id: uuid.UUID
    ) -> bool:
        """Delete a wallet connection."""
        db_wallet = self.get_wallet_connection(db, wallet_id)
        if not db_wallet:
            return False
        
        db.delete(db_wallet)
        db.commit()
        return True
    
    def verify_wallet_connection(
        self, 
        db: Session, 
        wallet_id: uuid.UUID,
        verification_method: str = "signature"
    ) -> Optional[WalletConnection]:
        """Verify a wallet connection."""
        db_wallet = self.get_wallet_connection(db, wallet_id)
        if not db_wallet:
            return None
        
        db_wallet.is_verified = True
        db_wallet.verification_method = verification_method
        db_wallet.verification_timestamp = datetime.utcnow()
        
        db.commit()
        db.refresh(db_wallet)
        return db_wallet
    
    def update_wallet_activity(
        self, 
        db: Session, 
        wallet_id: uuid.UUID
    ) -> Optional[WalletConnection]:
        """Update the last activity timestamp for a wallet."""
        db_wallet = self.get_wallet_connection(db, wallet_id)
        if not db_wallet:
            return None
        
        db_wallet.last_activity = datetime.utcnow()
        db.commit()
        db.refresh(db_wallet)
        return db_wallet


class WalletActivityCRUD:
    """CRUD operations for wallet activities."""
    
    def create_wallet_activity(
        self, 
        db: Session, 
        activity_data: WalletActivityCreate
    ) -> WalletActivity:
        """Create a new wallet activity record."""
        db_activity = WalletActivity(
            wallet_connection_id=activity_data.wallet_connection_id,
            activity_type=activity_data.activity_type,
            transaction_hash=activity_data.transaction_hash,
            block_number=activity_data.block_number,
            transaction_type=activity_data.transaction_type,
            from_address=activity_data.from_address,
            to_address=activity_data.to_address,
            token_address=activity_data.token_address,
            token_symbol=activity_data.token_symbol,
            token_name=activity_data.token_name,
            amount=activity_data.amount,
            amount_usd=activity_data.amount_usd,
            gas_used=activity_data.gas_used,
            gas_price=activity_data.gas_price,
            gas_fee_usd=activity_data.gas_fee_usd,
            network=activity_data.network,
            status=activity_data.status,
            timestamp=activity_data.timestamp,
            transaction_metadata=activity_data.transaction_metadata
        )
        
        db.add(db_activity)
        db.commit()
        db.refresh(db_activity)
        return db_activity
    
    def get_wallet_activities(
        self, 
        db: Session, 
        wallet_connection_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0
    ) -> List[WalletActivity]:
        """Get wallet activities for a connection."""
        return db.query(WalletActivity).filter(
            WalletActivity.wallet_connection_id == wallet_connection_id
        ).order_by(desc(WalletActivity.timestamp)).offset(offset).limit(limit).all()
    
    def get_wallet_analytics(
        self, 
        db: Session, 
        wallet_connection_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get analytics for a wallet connection."""
        query = db.query(WalletActivity).filter(
            WalletActivity.wallet_connection_id == wallet_connection_id
        )
        
        if start_date:
            query = query.filter(WalletActivity.timestamp >= start_date)
        if end_date:
            query = query.filter(WalletActivity.timestamp <= end_date)
        
        activities = query.all()
        
        if not activities:
            return {
                "total_transactions": 0,
                "total_volume_usd": Decimal('0'),
                "total_inflow_usd": Decimal('0'),
                "total_outflow_usd": Decimal('0'),
                "net_flow_usd": Decimal('0'),
                "unique_tokens": 0,
                "networks": [],
                "transaction_types": {},
                "daily_activity": [],
                "top_tokens": [],
                "top_addresses": [],
                "gas_spent_usd": Decimal('0'),
                "first_transaction": None,
                "last_transaction": None
            }
        
        # Get wallet connection to determine wallet address
        wallet_connection = db.query(WalletConnection).filter(
            WalletConnection.id == wallet_connection_id
        ).first()
        
        if not wallet_connection:
            return {
                "total_transactions": 0,
                "total_volume_usd": Decimal('0'),
                "total_inflow_usd": Decimal('0'),
                "total_outflow_usd": Decimal('0'),
                "net_flow_usd": Decimal('0'),
                "unique_tokens": 0,
                "networks": [],
                "transaction_types": {},
                "daily_activity": [],
                "top_tokens": [],
                "top_addresses": [],
                "gas_spent_usd": Decimal('0'),
                "first_transaction": None,
                "last_transaction": None
            }
        
        wallet_address = wallet_connection.wallet_address.lower()
        
        # Calculate analytics
        total_transactions = len(activities)
        
        # Calculate volume as inflow + outflow (actual wallet activity)
        total_volume_usd = Decimal('0')
        total_inflow_usd = Decimal('0')
        total_outflow_usd = Decimal('0')
        
        for activity in activities:
            from_address = (activity.from_address or '').lower() if activity.from_address else ''
            to_address = (activity.to_address or '').lower() if activity.to_address else ''
            amount_usd = activity.amount_usd or Decimal('0')
            
            if from_address == wallet_address and to_address != wallet_address:
                # Outgoing transaction (wallet is sender)
                total_outflow_usd += amount_usd
                total_volume_usd += amount_usd
            elif to_address == wallet_address and from_address != wallet_address:
                # Incoming transaction (wallet is receiver)
                total_inflow_usd += amount_usd
                total_volume_usd += amount_usd
            # Self-transactions are not counted in volume as they don't represent actual flow
        
        net_flow_usd = total_inflow_usd - total_outflow_usd
        
        unique_tokens = len(set(
            activity.token_address for activity in activities 
            if activity.token_address
        ))
        networks = list(set(activity.network for activity in activities))
        
        # Transaction types
        transaction_types = {}
        for activity in activities:
            tx_type = activity.transaction_type
            transaction_types[tx_type] = transaction_types.get(tx_type, 0) + 1
        
        # Daily activity with inflow/outflow
        daily_activity = {}
        for activity in activities:
            date_key = activity.timestamp.date().isoformat()
            if date_key not in daily_activity:
                daily_activity[date_key] = {
                    "transactions": 0, 
                    "volume_usd": Decimal('0'),
                    "inflow_usd": Decimal('0'),
                    "outflow_usd": Decimal('0'),
                    "net_flow_usd": Decimal('0')
                }
            
            daily_activity[date_key]["transactions"] += 1
            
            # Calculate inflow/outflow for this activity
            from_address = (activity.from_address or '').lower() if activity.from_address else ''
            to_address = (activity.to_address or '').lower() if activity.to_address else ''
            amount_usd = activity.amount_usd or Decimal('0')
            
            if from_address == wallet_address and to_address != wallet_address:
                # Outgoing transaction (wallet is sender)
                daily_activity[date_key]["outflow_usd"] += amount_usd
                daily_activity[date_key]["volume_usd"] += amount_usd  # Add to volume
            elif to_address == wallet_address and from_address != wallet_address:
                # Incoming transaction (wallet is receiver)
                daily_activity[date_key]["inflow_usd"] += amount_usd
                daily_activity[date_key]["volume_usd"] += amount_usd  # Add to volume
            # Self-transactions are not counted in volume as they don't represent actual flow
            
            daily_activity[date_key]["net_flow_usd"] = (
                daily_activity[date_key]["inflow_usd"] - daily_activity[date_key]["outflow_usd"]
            )
        
        # Top tokens (based on actual wallet activity - inflow + outflow)
        token_volumes = {}
        for activity in activities:
            if activity.token_symbol and activity.amount_usd:
                from_address = (activity.from_address or '').lower() if activity.from_address else ''
                to_address = (activity.to_address or '').lower() if activity.to_address else ''
                amount_usd = activity.amount_usd or Decimal('0')
                
                # Only count tokens that represent actual wallet activity
                if (from_address == wallet_address and to_address != wallet_address) or \
                   (to_address == wallet_address and from_address != wallet_address):
                    token = activity.token_symbol
                    token_volumes[token] = token_volumes.get(token, Decimal('0')) + amount_usd
        
        top_tokens = [
            {"symbol": token, "volume_usd": float(volume)}
            for token, volume in sorted(token_volumes.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        # Gas spent
        gas_spent_usd = sum(
            activity.gas_fee_usd or Decimal('0') for activity in activities
        )
        
        # First and last transactions
        timestamps = [activity.timestamp for activity in activities]
        first_transaction = min(timestamps) if timestamps else None
        last_transaction = max(timestamps) if timestamps else None
        
        # Calculate address interaction rankings
        address_interactions = {}
        try:
            for activity in activities:
                from_address = (activity.from_address or '').lower() if activity.from_address else ''
                to_address = (activity.to_address or '').lower() if activity.to_address else ''
                amount_usd = activity.amount_usd or Decimal('0')
                
                # Track interactions with other addresses (not self)
                if from_address == wallet_address and to_address != wallet_address:
                    # Outgoing to this address
                    if to_address not in address_interactions:
                        address_interactions[to_address] = {
                            'address': to_address,
                            'outgoing_count': 0,
                            'incoming_count': 0,
                            'outgoing_volume': Decimal('0'),
                            'incoming_volume': Decimal('0'),
                            'total_interactions': 0,
                            'net_flow': Decimal('0')
                        }
                    address_interactions[to_address]['outgoing_count'] += 1
                    address_interactions[to_address]['outgoing_volume'] += amount_usd
                    address_interactions[to_address]['total_interactions'] += 1
                    address_interactions[to_address]['net_flow'] -= amount_usd
                    
                elif to_address == wallet_address and from_address != wallet_address:
                    # Incoming from this address
                    if from_address not in address_interactions:
                        address_interactions[from_address] = {
                            'address': from_address,
                            'outgoing_count': 0,
                            'incoming_count': 0,
                            'outgoing_volume': Decimal('0'),
                            'incoming_volume': Decimal('0'),
                            'total_interactions': 0,
                            'net_flow': Decimal('0')
                        }
                    address_interactions[from_address]['incoming_count'] += 1
                    address_interactions[from_address]['incoming_volume'] += amount_usd
                    address_interactions[from_address]['total_interactions'] += 1
                    address_interactions[from_address]['net_flow'] += amount_usd
        except Exception as e:
            # If there's an error, set empty list
            address_interactions = {}
        
        # Sort addresses by total interactions (most frequent first)
        top_addresses = sorted(
            address_interactions.values(),
            key=lambda x: x['total_interactions'],
            reverse=True
        )[:10]  # Top 10 most interacted addresses
        
        # Convert Decimal to float for JSON serialization
        top_addresses_serialized = []
        for addr in top_addresses:
            top_addresses_serialized.append({
                'address': addr['address'],
                'outgoing_count': addr['outgoing_count'],
                'incoming_count': addr['incoming_count'],
                'outgoing_volume': float(addr['outgoing_volume']),
                'incoming_volume': float(addr['incoming_volume']),
                'total_interactions': addr['total_interactions'],
                'net_flow': float(addr['net_flow'])
            })
        
        return {
            "total_transactions": total_transactions,
            "total_volume_usd": total_volume_usd,
            "total_inflow_usd": total_inflow_usd,
            "total_outflow_usd": total_outflow_usd,
            "net_flow_usd": net_flow_usd,
            "unique_tokens": unique_tokens,
            "networks": networks,
            "transaction_types": transaction_types,
            "daily_activity": [
                {"date": date, **data} for date, data in daily_activity.items()
            ],
            "top_tokens": top_tokens,
            "top_addresses": top_addresses_serialized,
            "gas_spent_usd": gas_spent_usd,
            "first_transaction": first_transaction,
            "last_transaction": last_transaction
        }
    
    def get_transaction_by_hash(
        self, 
        db: Session, 
        transaction_hash: str
    ) -> Optional[WalletActivity]:
        """Get a transaction by hash."""
        return db.query(WalletActivity).filter(
            WalletActivity.transaction_hash == transaction_hash
        ).first()
    
    def get_recent_activities(
        self, 
        db: Session, 
        wallet_connection_id: uuid.UUID,
        hours: int = 24
    ) -> List[WalletActivity]:
        """Get recent activities within specified hours."""
        since = datetime.utcnow() - timedelta(hours=hours)
        return db.query(WalletActivity).filter(
            and_(
                WalletActivity.wallet_connection_id == wallet_connection_id,
                WalletActivity.timestamp >= since
            )
        ).order_by(desc(WalletActivity.timestamp)).all()
    
    def get_inflow_outflow_analytics(
        self, 
        db: Session, 
        wallet_connection_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get detailed inflow and outflow analytics for a wallet connection."""
        query = db.query(WalletActivity).filter(
            WalletActivity.wallet_connection_id == wallet_connection_id
        )
        
        if start_date:
            query = query.filter(WalletActivity.timestamp >= start_date)
        if end_date:
            query = query.filter(WalletActivity.timestamp <= end_date)
        
        activities = query.all()
        
        if not activities:
            return {
                "total_inflow_usd": Decimal('0'),
                "total_outflow_usd": Decimal('0'),
                "net_flow_usd": Decimal('0'),
                "inflow_transactions": 0,
                "outflow_transactions": 0,
                "inflow_by_token": {},
                "outflow_by_token": {},
                "inflow_by_network": {},
                "outflow_by_network": {},
                "daily_flow": []
            }
        
        # Get wallet connection to determine wallet address
        wallet_connection = db.query(WalletConnection).filter(
            WalletConnection.id == wallet_connection_id
        ).first()
        
        if not wallet_connection:
            return {
                "total_inflow_usd": Decimal('0'),
                "total_outflow_usd": Decimal('0'),
                "net_flow_usd": Decimal('0'),
                "inflow_transactions": 0,
                "outflow_transactions": 0,
                "inflow_by_token": {},
                "outflow_by_token": {},
                "inflow_by_network": {},
                "outflow_by_network": {},
                "daily_flow": []
            }
        
        wallet_address = wallet_connection.wallet_address.lower()
        
        # Calculate totals dynamically
        total_inflow_usd = Decimal('0')
        total_outflow_usd = Decimal('0')
        inflow_transactions = 0
        outflow_transactions = 0
        
        for activity in activities:
            from_address = (activity.from_address or '').lower()
            to_address = (activity.to_address or '').lower()
            amount_usd = activity.amount_usd or Decimal('0')
            
            if from_address == wallet_address and to_address != wallet_address:
                # Outgoing transaction (wallet is sender)
                total_outflow_usd += amount_usd
                outflow_transactions += 1
            elif to_address == wallet_address and from_address != wallet_address:
                # Incoming transaction (wallet is receiver)
                total_inflow_usd += amount_usd
                inflow_transactions += 1
        
        net_flow_usd = total_inflow_usd - total_outflow_usd
        
        # Group by token
        inflow_by_token = {}
        outflow_by_token = {}
        for activity in activities:
            token = activity.token_symbol or 'Unknown'
            from_address = (activity.from_address or '').lower()
            to_address = (activity.to_address or '').lower()
            amount_usd = activity.amount_usd or Decimal('0')
            
            if from_address == wallet_address and to_address != wallet_address:
                # Outgoing transaction (wallet is sender)
                outflow_by_token[token] = outflow_by_token.get(token, Decimal('0')) + amount_usd
            elif to_address == wallet_address and from_address != wallet_address:
                # Incoming transaction (wallet is receiver)
                inflow_by_token[token] = inflow_by_token.get(token, Decimal('0')) + amount_usd
        
        # Group by network
        inflow_by_network = {}
        outflow_by_network = {}
        for activity in activities:
            network = activity.network or 'Unknown'
            from_address = (activity.from_address or '').lower()
            to_address = (activity.to_address or '').lower()
            amount_usd = activity.amount_usd or Decimal('0')
            
            if from_address == wallet_address and to_address != wallet_address:
                # Outgoing transaction (wallet is sender)
                outflow_by_network[network] = outflow_by_network.get(network, Decimal('0')) + amount_usd
            elif to_address == wallet_address and from_address != wallet_address:
                # Incoming transaction (wallet is receiver)
                inflow_by_network[network] = inflow_by_network.get(network, Decimal('0')) + amount_usd
        
        # Daily flow
        daily_flow = {}
        for activity in activities:
            date_key = activity.timestamp.date().isoformat()
            if date_key not in daily_flow:
                daily_flow[date_key] = {
                    "inflow_usd": Decimal('0'),
                    "outflow_usd": Decimal('0'),
                    "net_flow_usd": Decimal('0'),
                    "inflow_count": 0,
                    "outflow_count": 0
                }
            
            from_address = (activity.from_address or '').lower()
            to_address = (activity.to_address or '').lower()
            amount_usd = activity.amount_usd or Decimal('0')
            
            if from_address == wallet_address and to_address != wallet_address:
                # Outgoing transaction (wallet is sender)
                daily_flow[date_key]["outflow_usd"] += amount_usd
                daily_flow[date_key]["outflow_count"] += 1
            elif to_address == wallet_address and from_address != wallet_address:
                # Incoming transaction (wallet is receiver)
                daily_flow[date_key]["inflow_usd"] += amount_usd
                daily_flow[date_key]["inflow_count"] += 1
            
            daily_flow[date_key]["net_flow_usd"] = (
                daily_flow[date_key]["inflow_usd"] - daily_flow[date_key]["outflow_usd"]
            )
        
        return {
            "total_inflow_usd": total_inflow_usd,
            "total_outflow_usd": total_outflow_usd,
            "net_flow_usd": net_flow_usd,
            "inflow_transactions": inflow_transactions,
            "outflow_transactions": outflow_transactions,
            "inflow_by_token": {token: float(amount) for token, amount in inflow_by_token.items()},
            "outflow_by_token": {token: float(amount) for token, amount in outflow_by_token.items()},
            "inflow_by_network": {network: float(amount) for network, amount in inflow_by_network.items()},
            "outflow_by_network": {network: float(amount) for network, amount in outflow_by_network.items()},
            "daily_flow": [
                {
                    "date": date,
                    "inflow_usd": float(data["inflow_usd"]),
                    "outflow_usd": float(data["outflow_usd"]),
                    "net_flow_usd": float(data["net_flow_usd"]),
                    "inflow_count": data["inflow_count"],
                    "outflow_count": data["outflow_count"]
                }
                for date, data in daily_flow.items()
            ]
        }


# Create instances
wallet_crud = WalletCRUD()
wallet_activity_crud = WalletActivityCRUD()
