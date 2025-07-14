# crud.py
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from .database import SessionLocal
from .models import User, PlatformMetrics  # Only import what exists in models.py
from enum import Enum

# Define PlatformType enum since it's used but not in models
class PlatformType(str, Enum):
    WEB2 = "web2"
    WEB3 = "web3"
    BOTH = "both"

# Type aliases
UserID = int
MetricID = int

# ----------- User Operations -----------
def create_user(
    db: Session,
    email: str,
    hashed_password: str,
    name: Optional[str] = None,
    country: Optional[str] = None,
    subscription_plan: str = "free",
    billing_id: Optional[str] = None,
    wallet_address: Optional[str] = None,
    wallet_type: Optional[str] = None,
) -> User:
    """
    Creates a new user with Web2/Web3 options
    Args:
        wallet_address: Crypto wallet (0x... or Solana format)
        wallet_type: 'metamask', 'phantom', etc.
    """
    db_user = User(
        email=email,
        hashed_password=hashed_password,
        name=name,
        country=country,
        subscription_plan=subscription_plan,
        billing_id=billing_id,
        wallet_address=wallet_address,
        wallet_type=wallet_type,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Case-sensitive email lookup"""
    return db.query(User).filter(User.email == email).first()

def get_user_by_wallet(db: Session, wallet_address: str) -> Optional[User]:
    """Case-insensitive wallet lookup"""
    return db.query(User).filter(User.wallet_address.ilike(wallet_address)).first()

def update_user_verification(db: Session, user_id: UserID, is_verified: bool) -> User:
    """Updates email verification status"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")
    setattr(user, "is_verified", is_verified)
    db.commit()
    db.refresh(user)
    return user

# ----------- Metrics Operations -----------
def get_user(db: Session, user_id: int) -> Optional[User]:
    """Retrieves a user by their ID"""
    return db.query(User).filter(User.id == user_id).first()
def create_platform_metric(
    db: Session,
    # Web2
    total_users: int = 0,
    active_sessions: int = 0,
    conversion_rate: float = 0.0,
    revenue_usd: float = 0.0,
    # Web3
    total_value_locked: float = 0.0,
    active_wallets: int = 0,
    transaction_volume_24h: float = 0.0,
    new_contracts: int = 0,
    # General
    daily_page_views: int = 0,
    sales_count: int = 0,
    platform: str = "both",  # Matches model's String(10) type
    source: Optional[str] = None,
    chain_id: Optional[int] = None,
    contract_address: Optional[str] = None,
) -> PlatformMetrics:
    """Creates metrics record matching model columns"""
    metric = PlatformMetrics(
        timestamp=datetime.utcnow(),
        # Web2
        total_users=total_users,
        active_sessions=active_sessions,
        conversion_rate=conversion_rate,
        revenue_usd=revenue_usd,
        # Web3
        total_value_locked=total_value_locked,
        active_wallets=active_wallets,
        transaction_volume_24h=transaction_volume_24h,
        new_contracts=new_contracts,
        # General
        daily_page_views=daily_page_views,
        sales_count=sales_count,
        platform=platform,
        source=source,
        chain_id=chain_id,
        contract_address=contract_address,
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric

def get_metrics_by_timeframe(
    db: Session,
    start: datetime,
    end: datetime,
    platform: Optional[str] = None,
    chain_id: Optional[int] = None,
) -> List[PlatformMetrics]:
    """Gets metrics filtered by time and optional platform/chain"""
    query = db.query(PlatformMetrics).filter(
        PlatformMetrics.timestamp >= start,
        PlatformMetrics.timestamp <= end
    )
    
    if platform:
        query = query.filter(PlatformMetrics.platform == platform)
    if chain_id:
        query = query.filter(PlatformMetrics.chain_id == chain_id)
        
    return query.order_by(PlatformMetrics.timestamp.asc()).all()

# ----------- Analytics Helpers -----------
def calculate_growth_rate(db: Session, days: int = 30) -> float:
    """Calculates percentage growth over period"""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    
    # Get scalar values explicitly
    start_metrics = db.query(PlatformMetrics.total_users).filter(
        PlatformMetrics.timestamp >= start,
        PlatformMetrics.timestamp <= start + timedelta(hours=24)
    ).scalar() or 1  # Default to 1 if None
    
    end_metrics = db.query(PlatformMetrics.total_users).filter(
        PlatformMetrics.timestamp >= end - timedelta(hours=24),
        PlatformMetrics.timestamp <= end
    ).scalar() or 0  # Default to 0 if None
    
    # Convert to float explicitly
    start_value = float(start_metrics)
    end_value = float(end_metrics)
    
    return ((end_value - start_value) / start_value) * 100

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()