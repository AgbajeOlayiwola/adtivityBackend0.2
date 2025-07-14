# models.py
from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, Boolean, Numeric
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False)
    signup_date = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Profile Data
    name = Column(String(100))
    country = Column(String(2))  # ISO 3166-1 alpha-2
    
    # Subscription Info
    subscription_plan = Column(String(20), default="free")  # free|pro|enterprise
    billing_id = Column(String(255))  # Stripe ID or Crypto Wallet
    
    # Web3 Specific
    wallet_address = Column(String(42), unique=True, index=True)  # For Web3 auth
    wallet_type = Column(String(10))  # metamask|phantom|etc

class PlatformMetrics(Base):
    __tablename__ = "platform_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Web2 Metrics
    total_users = Column(Integer, default=0)
    active_sessions = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)  # 0.0-1.0 scale
    revenue_usd = Column(Numeric(12, 2), default=0.0)  # Standard currency
    
    # Web3 Metrics
    total_value_locked = Column(Numeric(24, 18), default=0.0)  # Crypto precision
    active_wallets = Column(Integer, default=0)
    transaction_volume_24h = Column(Numeric(24, 18), default=0.0)
    new_contracts = Column(Integer, default=0)
    
    # Cross-Platform
    daily_page_views = Column(Integer, default=0)
    sales_count = Column(Integer, default=0)
    
    # Dimensions
    platform = Column(String(10), default="both")  # web2|web3|both
    source = Column(String(50))  # Marketing attribution
    
    # Chain Metadata (for Web3)
    chain_id = Column(Integer)  # EVM chain ID
    contract_address = Column(String(42))  # Primary contract