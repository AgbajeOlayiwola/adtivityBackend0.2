# models.py
# This file is like a blueprint for our database tables. It defines what
# each table looks like, what kind of information it holds, and how
# the tables relate to each other.

# --- Step 1: Get Our Tools Ready for Building! ---
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, DECIMAL, Date, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
import uuid
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint, Index, Float
from datetime import date

# The `declarative_base()` is a class that lets us define our tables as Python classes.
Base = declarative_base()

# --- Step 2: Define the Tables (Blueprints) ---

class PlatformUser(Base):
    """
    Blueprint for the 'platform_users' table.
    These are the users of *your Adtivity platform*.
    """
    __tablename__ = "platform_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
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
    
    # Twitter integration relationships
    # twitter_accounts = relationship("TwitterAccount", back_populates="platform_user")


class ClientCompany(Base):
    """
    Blueprint for the 'client_companies' table.
    These are the companies that use your SDK.
    """
    __tablename__ = "client_companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, index=True, nullable=False)
    api_key_hash = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    is_twitter_added = Column(Boolean, default=False, comment="Whether Twitter integration has been added")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # A foreign key to link this company to a PlatformUser.
    platform_user_id = Column(UUID(as_uuid=True), ForeignKey("platform_users.id"), nullable=False)
    
    # The relationship with the PlatformUser table.
    platform_user = relationship("PlatformUser", back_populates="client_companies")

    # NEW: Relationships to link this company to its Web2 and Web3 events.
    events = relationship("Event", back_populates="client_company")
    web3_events = relationship("Web3Event", back_populates="client_company")
    app_users = relationship("ClientAppUser", back_populates="company")
    twitter_accounts = relationship("CompanyTwitter", back_populates="company")
    mention_notifications = relationship("MentionNotification", back_populates="company")
    wallet_connections = relationship("WalletConnection", back_populates="company")


class ClientAppUser(Base):
    """
    Blueprint for the 'client_app_users' table.
    These are the end-users of your client companies' apps.
    """
    __tablename__ = "client_app_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, index=True, unique=True)
    hashed_password = Column(String)
    name = Column(String)
    country = Column(String(2))
    region = Column(String(100))  # State/province/region
    city = Column(String(100))    # City name
    wallet_address = Column(String, index=True, unique=True)
    wallet_type = Column(String)
    is_verified = Column(Boolean, default=False)
    subscription_plan = Column(String, default="free")
    billing_id = Column(String)
    
    # Foreign key relationships
    company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=True)
    platform_user_id = Column(UUID(as_uuid=True), ForeignKey("platform_users.id"), nullable=True)
    user_id = Column(String, nullable=True)  # For linking to external user IDs
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))
    
    # Relationships
    company = relationship("ClientCompany", back_populates="app_users")
    platform_user = relationship("PlatformUser")


class LoginAttempt(Base):
    """
    Blueprint for tracking login attempts for security.
    """
    __tablename__ = "login_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, index=True, nullable=False)
    ip_address = Column(String, nullable=False)
    user_agent = Column(String)
    success = Column(Boolean, default=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Index for efficient querying
    __table_args__ = (
        Index('idx_login_attempts_email_timestamp', 'email', 'timestamp'),
        Index('idx_login_attempts_ip_timestamp', 'ip_address', 'timestamp'),
    )


class PasswordResetToken(Base):
    """Password reset token model."""
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


# Twitter Integration Models
class CompanyTwitter(Base):
    """Company Twitter account model."""
    __tablename__ = "company_twitter"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=False, index=True)
    twitter_handle = Column(String, nullable=False, unique=True, index=True)
    twitter_user_id = Column(String, nullable=True, index=True)
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    tweets_count = Column(Integer, default=0)
    profile_image_url = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    verified = Column(Boolean, default=False)
    last_updated = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    company = relationship("ClientCompany", back_populates="twitter_accounts")
    tweets = relationship("TwitterTweet", back_populates="company_twitter")
    followers = relationship("TwitterFollower", back_populates="company_twitter")


class TwitterTweet(Base):
    """Twitter tweet model."""
    __tablename__ = "twitter_tweets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tweet_id = Column(String, nullable=False, unique=True, index=True)
    company_twitter_id = Column(UUID(as_uuid=True), ForeignKey("company_twitter.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    retweet_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    quote_count = Column(Integer, default=0)
    hashtags = Column(JSON, nullable=True)  # Store hashtags as JSON array
    mentions = Column(JSON, nullable=True)  # Store mentions as JSON array
    collected_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    company_twitter = relationship("CompanyTwitter", back_populates="tweets")


class TwitterFollower(Base):
    """Twitter follower model."""
    __tablename__ = "twitter_followers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    follower_id = Column(String, nullable=False, index=True)
    company_twitter_id = Column(UUID(as_uuid=True), ForeignKey("company_twitter.id"), nullable=False, index=True)
    username = Column(String, nullable=False, index=True)
    display_name = Column(String, nullable=True)
    profile_image_url = Column(String, nullable=True)
    verified = Column(Boolean, default=False)
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    tweets_count = Column(Integer, default=0)
    followed_at = Column(DateTime(timezone=True), nullable=True)
    collected_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    company_twitter = relationship("CompanyTwitter", back_populates="followers")


class HashtagMention(Base):
    """Simple hashtag mention tracking."""
    __tablename__ = "hashtag_mentions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=False, index=True)
    hashtag = Column(String, nullable=False, index=True)
    tweet_id = Column(String, nullable=False, index=True)
    username = Column(String, nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    engagement = Column(Integer, default=0)  # Combined likes + retweets + replies
    collected_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class TwitterAnalytics(Base):
    """Daily Twitter analytics model."""
    __tablename__ = "twitter_analytics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_twitter_id = Column(UUID(as_uuid=True), ForeignKey("company_twitter.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    total_tweets = Column(Integer, default=0)
    total_likes = Column(Integer, default=0)
    total_retweets = Column(Integer, default=0)
    total_replies = Column(Integer, default=0)
    total_mentions = Column(Integer, default=0)
    followers_gained = Column(Integer, default=0)
    followers_lost = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    reach_estimate = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    company_twitter = relationship("CompanyTwitter")
    
    # Composite unique constraint
    __table_args__ = (UniqueConstraint('company_twitter_id', 'date', name='unique_company_date'),)


class MentionNotification(Base):
    """Mention notification preferences model."""
    __tablename__ = "mention_notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=False, index=True)
    twitter_handle = Column(String, nullable=False, index=True)
    notification_email = Column(String, nullable=True)
    notification_webhook = Column(String, nullable=True)
    mention_keywords = Column(JSON, nullable=True)  # Store keywords as JSON array
    is_active = Column(Boolean, default=True)
    last_notification_sent = Column(DateTime(timezone=True), nullable=True)
    notification_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("ClientCompany", back_populates="mention_notifications")


class Event(Base):
    """
    Blueprint for the 'events' table.
    This stores all the standard Web2 SDK events sent from client apps.
    """
    __tablename__ = "events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    event_name = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    user_id = Column(String)
    anonymous_id = Column(String)
    session_id = Column(String)
    properties = Column(JSON, default={})
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Region tracking fields
    country = Column(String(2), index=True)  # ISO 3166-1 alpha-2 country code
    region = Column(String(100), index=True)  # State/province/region
    city = Column(String(100), index=True)   # City name
    ip_address = Column(String(45), index=True)  # IPv4 or IPv6 address
    
    # A foreign key to link the event to the company that sent it.
    client_company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=False)

    # The relationship with the ClientCompany table.
    client_company = relationship("ClientCompany", back_populates="events")


# --- NEW: Web3 Event Blueprint ---
class Web3Event(Base):
    """
    Blueprint for the 'web3_events' table.
    This stores all the Web3-specific SDK events.
    """
    __tablename__ = "web3_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(String, nullable=False)
    event_name = Column(String, nullable=False)
    wallet_address = Column(String, nullable=False, index=True)
    chain_id = Column(String, nullable=False, index=True)
    transaction_hash = Column(String, nullable=True, index=True)
    contract_address = Column(String, nullable=True, index=True)
    properties = Column(JSON, default={})
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Region tracking fields
    country = Column(String(2), index=True)  # ISO 3166-1 alpha-2 country code
    region = Column(String(100), index=True)  # State/province/region
    city = Column(String(100), index=True)   # City name
    ip_address = Column(String(45), index=True)  # IPv4 or IPv6 address

    # A foreign key to link the Web3 event to the company that sent it.
    client_company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=False)

    # The relationship with the ClientCompany table.
    client_company = relationship("ClientCompany", back_populates="web3_events")


class PlatformMetrics(Base):
    """
    Blueprint for the 'platform_metrics' table.
    This table stores aggregated metrics for your clients' apps.
    """
    __tablename__ = "platform_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
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
    
    # Region tracking dimensions
    country = Column(String(2), index=True)  # ISO 3166-1 alpha-2 country code
    region = Column(String(100), index=True)  # State/province/region
    city = Column(String(100), index=True)   # City name
    
    # A foreign key to link metrics to a specific client company
    client_company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=False)

# ====================================================================================
# --- Data Aggregation Models ---
# ====================================================================================

class RawEvent(Base):
    """Raw event storage for Enterprise customers - full granularity."""
    __tablename__ = "raw_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=False, index=True)
    campaign_id = Column(String, nullable=False, index=True)
    event_name = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    user_id = Column(String, index=True)
    anonymous_id = Column(String, index=True)
    session_id = Column(String, index=True)
    
    # Full event properties
    properties = Column(JSON, default={})
    
    # Geographic data
    country = Column(String(2), index=True)
    region = Column(String(100), index=True)
    city = Column(String(100), index=True)
    ip_address = Column(String(45), index=True)
    
    # Timestamps
    event_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    company = relationship("ClientCompany")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_raw_events_company_campaign', 'company_id', 'campaign_id'),
        Index('idx_raw_events_timestamp', 'event_timestamp'),
        Index('idx_raw_events_type_name', 'event_type', 'event_name'),
    )


class CampaignAnalyticsDaily(Base):
    """Daily aggregated analytics for Basic Plan customers."""
    __tablename__ = "campaign_analytics_daily"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=False, index=True)
    campaign_id = Column(String, nullable=False, index=True)
    analytics_date = Column(Date, nullable=False, index=True)
    
    # Event counts by type
    event_counts = Column(JSON, default={})  # {"page_view": 1500, "purchase": 45, "signup": 23}
    
    # Geographic aggregation
    country_breakdown = Column(JSON, default={})  # {"US": 1200, "UK": 300}
    region_breakdown = Column(JSON, default={})
    city_breakdown = Column(JSON, default={})
    
    # User metrics
    unique_users = Column(Integer, default=0)
    new_users = Column(Integer, default=0)
    returning_users = Column(Integer, default=0)
    
    # Conversion metrics
    conversion_rate = Column(Float, default=0.0)
    campaign_revenue_usd = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("ClientCompany")
    
    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint('company_id', 'campaign_id', 'analytics_date', name='unique_campaign_daily'),
        Index('idx_campaign_daily_date', 'analytics_date'),
        Index('idx_campaign_daily_campaign', 'campaign_id'),
    )


class CampaignAnalyticsHourly(Base):
    """Hourly aggregated analytics for Pro Plan customers."""
    __tablename__ = "campaign_analytics_hourly"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=False, index=True)
    campaign_id = Column(String, nullable=False, index=True)
    analytics_date = Column(Date, nullable=False, index=True)
    hour = Column(Integer, nullable=False, index=True)  # 0-23
    
    # Event counts by type (hourly)
    event_counts = Column(JSON, default={})
    
    # Geographic aggregation (hourly)
    country_breakdown = Column(JSON, default={})
    region_breakdown = Column(JSON, default={})
    city_breakdown = Column(JSON, default={})
    
    # User metrics (hourly)
    unique_users = Column(Integer, default=0)
    new_users = Column(Integer, default=0)
    returning_users = Column(Integer, default=0)
    
    # Conversion metrics (hourly)
    conversion_rate = Column(Float, default=0.0)
    campaign_revenue_usd = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("ClientCompany")
    
    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint('company_id', 'campaign_id', 'analytics_date', 'hour', name='unique_campaign_hourly'),
        Index('idx_campaign_hourly_datetime', 'analytics_date', 'hour'),
        Index('idx_campaign_hourly_campaign', 'campaign_id'),
    )


class SubscriptionPlan(Base):
    """Customer subscription plans for data aggregation tiers."""
    __tablename__ = "subscription_plans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=False, index=True)
    
    # Plan details
    plan_name = Column(String, nullable=False)  # "basic", "pro", "enterprise"
    plan_tier = Column(Integer, nullable=False)  # 1=basic, 2=pro, 3=enterprise
    
    # Data retention settings
    raw_data_retention_days = Column(Integer, default=0)  # 0 = no raw data
    aggregation_frequency = Column(String, default="daily")  # "daily", "hourly", "real_time"
    
    # Storage limits
    max_raw_events_per_month = Column(Integer, default=0)
    max_aggregated_rows_per_month = Column(Integer, default=100000)
    
    # Pricing
    monthly_price_usd = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("ClientCompany")
    
    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint('company_id', 'plan_name', name='unique_company_plan'),
    )


class WalletConnection(Base):
    """
    Blueprint for the 'wallet_connections' table.
    Stores wallet connections for Web3 analytics.
    """
    __tablename__ = "wallet_connections"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=False, index=True)
    wallet_address = Column(String, nullable=False, index=True)  # The actual wallet address
    wallet_type = Column(String, nullable=False)  # 'metamask', 'solflare', 'phantom', etc.
    network = Column(String, nullable=False)  # 'ethereum', 'solana', 'polygon', etc.
    wallet_name = Column(String)  # User-friendly name for the wallet
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)  # Whether the wallet is verified
    verification_method = Column(String)  # 'signature', 'transaction', etc.
    verification_timestamp = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True))
    
    # Relationships
    company = relationship("ClientCompany", back_populates="wallet_connections")
    
    # Ensure unique wallet address per company
    __table_args__ = (
        UniqueConstraint('company_id', 'wallet_address', name='unique_company_wallet'),
        Index('idx_wallet_address', 'wallet_address'),
        Index('idx_company_wallet', 'company_id', 'wallet_address'),
    )


class WalletActivity(Base):
    """
    Blueprint for the 'wallet_activities' table.
    Stores wallet activity and transaction data for analytics.
    """
    __tablename__ = "wallet_activities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    wallet_connection_id = Column(UUID(as_uuid=True), ForeignKey("wallet_connections.id"), nullable=False, index=True)
    activity_type = Column(String, nullable=False)  # Required field for database compatibility
    transaction_hash = Column(String, nullable=False, index=True)
    block_number = Column(Integer)
    transaction_type = Column(String, nullable=False)  # 'send', 'receive', 'swap', 'mint', etc.
    from_address = Column(String, index=True)
    to_address = Column(String, index=True)
    token_address = Column(String, index=True)  # For token transactions
    token_symbol = Column(String)
    token_name = Column(String)
    amount = Column(DECIMAL(36, 18))  # Large precision for crypto amounts
    amount_usd = Column(DECIMAL(15, 2))  # USD value at time of transaction
    gas_used = Column(Integer)
    gas_price = Column(DECIMAL(36, 18))
    gas_fee_usd = Column(DECIMAL(15, 2))
    network = Column(String, nullable=False)
    status = Column(String, default='confirmed')  # 'pending', 'confirmed', 'failed'
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Additional metadata
    transaction_metadata = Column(JSON)  # Store additional transaction data
    
    # Relationships
    wallet_connection = relationship("WalletConnection")
    
    # Indexes for better query performance
    __table_args__ = (
        Index('idx_wallet_timestamp', 'wallet_connection_id', 'timestamp'),
        Index('idx_transaction_hash', 'transaction_hash'),
        Index('idx_token_address', 'token_address'),
        Index('idx_network_timestamp', 'network', 'timestamp'),
    )


# ====================================================================================
# --- User Engagement Tracking Models ---
# ====================================================================================

class UserSession(Base):
    """
    Blueprint for the 'user_sessions' table.
    Tracks user sessions for engagement analytics.
    """
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)  # Can be user_id or anonymous_id
    session_id = Column(String, nullable=False, index=True)
    
    # Session timing
    session_start = Column(DateTime(timezone=True), nullable=False, index=True)
    session_end = Column(DateTime(timezone=True), nullable=True, index=True)
    last_activity = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Engagement metrics
    total_events = Column(Integer, default=0)
    active_time_seconds = Column(Integer, default=0)  # Total time user was actively engaged
    page_views = Column(Integer, default=0)
    unique_pages = Column(Integer, default=0)
    
    # Geographic data
    country = Column(String(2), index=True)
    region = Column(String(100), index=True)
    city = Column(String(100), index=True)
    ip_address = Column(String(45), index=True)
    
    # Session metadata
    user_agent = Column(String)
    referrer = Column(String)
    device_type = Column(String)  # 'mobile', 'desktop', 'tablet'
    browser = Column(String)
    os = Column(String)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("ClientCompany")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_session_company', 'company_id', 'user_id'),
        Index('idx_session_timing', 'session_start', 'session_end'),
        Index('idx_user_activity', 'user_id', 'last_activity'),
        Index('idx_company_session', 'company_id', 'session_id'),
    )


class UserEngagement(Base):
    """
    Blueprint for the 'user_engagement' table.
    Tracks detailed user engagement metrics.
    """
    __tablename__ = "user_engagement"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)
    
    # Engagement tracking
    event_name = Column(String, nullable=False, index=True)
    event_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    engagement_duration_seconds = Column(Integer, default=0)  # Time spent on this specific event/page
    
    # Event context
    page_url = Column(String)
    page_title = Column(String)
    event_properties = Column(JSON, default={})
    
    # Geographic data
    country = Column(String(2), index=True)
    region = Column(String(100), index=True)
    city = Column(String(100), index=True)
    ip_address = Column(String(45), index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    company = relationship("ClientCompany")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_engagement_company', 'company_id', 'user_id'),
        Index('idx_engagement_timing', 'event_timestamp'),
        Index('idx_session_engagement', 'session_id', 'event_timestamp'),
        Index('idx_user_events', 'user_id', 'event_timestamp'),
    )


class UserActivitySummary(Base):
    """
    Blueprint for the 'user_activity_summary' table.
    Daily/hourly aggregated user activity metrics.
    """
    __tablename__ = "user_activity_summary"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("client_companies.id"), nullable=False, index=True)
    
    # Time period
    summary_date = Column(Date, nullable=False, index=True)
    hour = Column(Integer, nullable=True, index=True)  # 0-23, null for daily summaries
    
    # User metrics
    total_active_users = Column(Integer, default=0)  # Users who had at least one event
    total_new_users = Column(Integer, default=0)  # Users seen for the first time
    total_returning_users = Column(Integer, default=0)  # Users who were active before
    
    # Engagement metrics
    total_sessions = Column(Integer, default=0)
    total_engagement_time_seconds = Column(Integer, default=0)
    avg_engagement_time_per_user = Column(Float, default=0.0)
    avg_engagement_time_per_session = Column(Float, default=0.0)
    
    # Event metrics
    total_events = Column(Integer, default=0)
    total_page_views = Column(Integer, default=0)
    unique_pages_viewed = Column(Integer, default=0)
    
    # Geographic breakdown
    country_breakdown = Column(JSON, default={})  # {"US": 150, "UK": 75}
    region_breakdown = Column(JSON, default={})
    city_breakdown = Column(JSON, default={})
    
    # Device breakdown
    device_breakdown = Column(JSON, default={})  # {"mobile": 200, "desktop": 150}
    browser_breakdown = Column(JSON, default={})
    operating_system_breakdown = Column(JSON, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("ClientCompany")
    
    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint('company_id', 'summary_date', 'hour', name='unique_company_date_hour'),
        Index('idx_activity_date', 'summary_date'),
        Index('idx_activity_company_date', 'company_id', 'summary_date'),
    )
