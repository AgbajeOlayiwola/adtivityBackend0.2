# models.py
# This file is like a blueprint for our database tables. It defines what
# each table looks like, what kind of information it holds, and how
# the tables relate to each other.

# --- Step 1: Get Our Tools Ready for Building! ---
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, DECIMAL
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

# The `declarative_base()` is a class that lets us define our tables as Python classes.
Base = declarative_base()

# --- Step 2: Define the Tables (Blueprints) ---

class PlatformUser(Base):
    """
    Blueprint for the 'platform_users' table.
    These are the users of *your Adtivity platform*.
    """
    __tablename__ = "platform_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String)
    phone_number = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))

    # A relationship to link PlatformUsers to the companies they own.
    # The `back_populates` links this relationship to the one in `ClientCompany`.
    client_companies = relationship("ClientCompany", back_populates="platform_user")


class ClientCompany(Base):
    """
    Blueprint for the 'client_companies' table.
    These are the companies that use your SDK.
    """
    __tablename__ = "client_companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    api_key_hash = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # A foreign key to link this company to a PlatformUser.
    platform_user_id = Column(Integer, ForeignKey("platform_users.id"), nullable=False)
    
    # The relationship with the PlatformUser table.
    platform_user = relationship("PlatformUser", back_populates="client_companies")

    # NEW: Relationships to link this company to its Web2 and Web3 events.
    events = relationship("Event", back_populates="client_company")
    web3_events = relationship("Web3Event", back_populates="client_company")


class ClientAppUser(Base):
    """
    Blueprint for the 'client_app_users' table.
    These are the end-users of your client companies' apps.
    """
    __tablename__ = "client_app_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, unique=True)
    hashed_password = Column(String)
    name = Column(String)
    country = Column(String(2))
    wallet_address = Column(String, index=True, unique=True)
    wallet_type = Column(String)
    is_verified = Column(Boolean, default=False)
    subscription_plan = Column(String, default="free")
    billing_id = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))


class Event(Base):
    """
    Blueprint for the 'events' table.
    This stores all the standard Web2 SDK events sent from client apps.
    """
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    user_id = Column(String)
    anonymous_id = Column(String)
    session_id = Column(String)
    properties = Column(JSON, default={})
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # A foreign key to link the event to the company that sent it.
    client_company_id = Column(Integer, ForeignKey("client_companies.id"), nullable=False)

    # The relationship with the ClientCompany table.
    client_company = relationship("ClientCompany", back_populates="events")


# --- NEW: Web3 Event Blueprint ---
class Web3Event(Base):
    """
    Blueprint for the 'web3_events' table.
    This stores all the Web3-specific SDK events.
    """
    __tablename__ = "web3_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False)
    event_name = Column(String, nullable=False)
    wallet_address = Column(String, nullable=False, index=True)
    chain_id = Column(String, nullable=False, index=True)
    transaction_hash = Column(String, nullable=True, index=True)
    contract_address = Column(String, nullable=True, index=True)
    properties = Column(JSON, default={})
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # A foreign key to link the Web3 event to the company that sent it.
    client_company_id = Column(Integer, ForeignKey("client_companies.id"), nullable=False)

    # The relationship with the ClientCompany table.
    client_company = relationship("ClientCompany", back_populates="web3_events")


class PlatformMetrics(Base):
    """
    Blueprint for the 'platform_metrics' table.
    This table stores aggregated metrics for your clients' apps.
    """
    __tablename__ = "platform_metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Metrics for Web2
    total_users = Column(Integer, default=0)
    active_sessions = Column(Integer, default=0)
    conversion_rate = Column(DECIMAL(10, 4), default=0.0)
    revenue_usd = Column(DECIMAL(10, 2), default=0.0)
    
    # Metrics for Web3
    total_value_locked = Column(DECIMAL(38, 18), default=0.0)
    active_wallets = Column(Integer, default=0)
    transaction_volume_24h = Column(DECIMAL(38, 18), default=0.0)
    new_contracts = Column(Integer, default=0)
    
    # General Metrics
    daily_page_views = Column(Integer, default=0)
    sales_count = Column(Integer, default=0)
    
    # Dimensions for filtering/segmenting metrics
    platform = Column(String, nullable=False, default="both")
    source = Column(String)
    chain_id = Column(String) # FIX: Changed from Integer to String to support chain IDs like '0x1'
    contract_address = Column(String)
    
    # A foreign key to link metrics to a specific client company
    client_company_id = Column(Integer, ForeignKey("client_companies.id"), nullable=False)
