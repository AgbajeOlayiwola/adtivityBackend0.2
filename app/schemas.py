# schemas.py
from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime
from typing import Optional
from enum import Enum
from decimal import Decimal

class PlatformType(str, Enum):
    WEB2 = "web2"
    WEB3 = "web3"
    BOTH = "both"

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, min_length=2, max_length=2)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    wallet_address: Optional[str] = Field(
        None,
        pattern=r'^0x[a-fA-F0-9]{40}$'  # Using pattern instead of regex
    )
    wallet_type: Optional[str] = Field(
        None,
        pattern=r'^0x[a-fA-F0-9]{40}$'  # Using pattern instead of regex
    )

class User(UserBase):
    id: int
    is_verified: bool
    signup_date: datetime
    subscription_plan: str
    last_login: Optional[datetime]
    wallet_address: Optional[str]
    wallet_type: Optional[str]

    class Config:
        from_attributes = True

class MetricsBase(BaseModel):
    # Web2
    total_users: int = 0
    active_sessions: int = 0
    conversion_rate: float = Field(0.0, ge=0, le=1)
    revenue_usd: Decimal = Decimal('0.00')
    
    # Web3
    total_value_locked: Decimal = Decimal('0.000000000000000000')
    active_wallets: int = 0
    transaction_volume_24h: Decimal = Decimal('0.000000000000000000')
    new_contracts: int = 0
    
    # General
    daily_page_views: int = 0
    sales_count: int = 0
    
    # Dimensions
    platform: PlatformType = PlatformType.BOTH
    source: Optional[str] = None
    chain_id: Optional[int] = None
    contract_address: Optional[str] = Field(
        None,
        pattern=r'^0x[a-fA-F0-9]{40}$'  # Using pattern instead of regex
    )

class MetricsCreate(MetricsBase):
    pass

class PlatformMetrics(MetricsBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True