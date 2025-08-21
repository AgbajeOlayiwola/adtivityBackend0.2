"""Metrics-related CRUD operations."""

from typing import List, Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import PlatformMetrics


def create_platform_metric(
    db: Session,
    client_company_id: uuid.UUID,
    total_users: int = 0,
    active_sessions: int = 0,
    conversion_rate: float = 0.0,
    revenue_usd: float = 0.0,
    total_value_locked: float = 0.0,
    active_wallets: int = 0,
    transaction_volume_24h: float = 0.0,
    new_contracts: int = 0,
    daily_page_views: int = 0,
    sales_count: int = 0,
    platform: str = "both",
    source: Optional[str] = None,
    chain_id: Optional[str] = None,
    contract_address: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    # New region tracking fields
    country: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
) -> PlatformMetrics:
    """Create a new platform metric."""
    db_metric = PlatformMetrics(
        client_company_id=client_company_id,
        total_users=total_users,
        active_sessions=active_sessions,
        conversion_rate=conversion_rate,
        revenue_usd=revenue_usd,
        total_value_locked=total_value_locked,
        active_wallets=active_wallets,
        transaction_volume_24h=transaction_volume_24h,
        new_contracts=new_contracts,
        daily_page_views=daily_page_views,
        sales_count=sales_count,
        platform=platform,
        source=source,
        chain_id=chain_id,
        contract_address=contract_address,
        timestamp=timestamp or datetime.now(timezone.utc),
        # New region tracking fields
        country=country,
        region=region,
        city=city,
    )
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    return db_metric


def get_metrics_by_timeframe_for_companies(
    db: Session,
    company_ids: List[uuid.UUID],
    start: datetime,
    end: datetime,
    platform: str = "both",
    chain_id: Optional[str] = None,
) -> List[PlatformMetrics]:
    """Get metrics for multiple companies within a time frame."""
    query = db.query(PlatformMetrics).filter(
        PlatformMetrics.client_company_id.in_(company_ids),
        PlatformMetrics.timestamp >= start,
        PlatformMetrics.timestamp <= end
    )
    
    if platform != "both":
        query = query.filter(PlatformMetrics.platform == platform)
    
    if chain_id:
        query = query.filter(PlatformMetrics.chain_id == chain_id)
    
    return query.order_by(PlatformMetrics.timestamp.desc()).all()


def calculate_growth_rate(
    current_value: float, previous_value: float
) -> float:
    """Calculate growth rate between two values."""
    if previous_value == 0:
        return 0.0 if current_value == 0 else 100.0
    
    return ((current_value - previous_value) / previous_value) * 100


def get_all_events_for_user(
    db: Session, platform_user_id: uuid.UUID
) -> List:
    """Get all events for companies owned by a platform user."""
    # This would need to be implemented based on your specific requirements
    # For now, returning an empty list
    return [] 