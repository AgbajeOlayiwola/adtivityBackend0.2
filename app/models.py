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
    hashtag_campaigns = relationship("HashtagCampaign", back_populates="company")


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
    token = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


# Twitter Integration Models
class CompanyTwitter(Base):
    """Company Twitter account model."""
    __tablename__ = "company_twitter"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("client_companies.id"), nullable=False, index=True)
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
    
    id = Column(Integer, primary_key=True, index=True)
    tweet_id = Column(String, nullable=False, unique=True, index=True)
    company_twitter_id = Column(Integer, ForeignKey("company_twitter.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    retweet_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    quote_count = Column(Integer, default=0)
    hashtags = Column(JSON, nullable=True)  # Store hashtags as JSON array
    mentions = Column(JSON, nullable=True)  # Store mentions as JSON array
    sentiment_score = Column(Float, nullable=True)
    sentiment_label = Column(String, nullable=True)
    collected_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    company_twitter = relationship("CompanyTwitter", back_populates="tweets")


class TwitterFollower(Base):
    """Twitter follower model."""
    __tablename__ = "twitter_followers"
    
    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(String, nullable=False, index=True)
    company_twitter_id = Column(Integer, ForeignKey("company_twitter.id"), nullable=False, index=True)
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


class HashtagCampaign(Base):
    """Hashtag campaign model."""
    __tablename__ = "hashtag_campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("client_companies.id"), nullable=False, index=True)
    hashtag = Column(String, nullable=False, index=True)
    campaign_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    target_mentions = Column(Integer, default=0)
    current_mentions = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    company = relationship("ClientCompany", back_populates="hashtag_campaigns")
    mentions = relationship("HashtagMention", back_populates="campaign")


class HashtagMention(Base):
    """Hashtag mention model."""
    __tablename__ = "hashtag_mentions"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("hashtag_campaigns.id"), nullable=False, index=True)
    tweet_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    username = Column(String, nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    retweet_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    sentiment_score = Column(Float, nullable=True)
    sentiment_label = Column(String, nullable=True)
    collected_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    campaign = relationship("HashtagCampaign", back_populates="mentions")


class TwitterAnalytics(Base):
    """Twitter analytics summary model."""
    __tablename__ = "twitter_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    company_twitter_id = Column(Integer, ForeignKey("company_twitter.id"), nullable=False, index=True)
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
# --- Twitter Integration Models ---
# ====================================================================================

# class TwitterAccount(Base):
#     """Twitter account connection and basic info."""
#     __tablename__ = "twitter_accounts"
#     
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     platform_user_id = Column(UUID(as_uuid=True), ForeignKey("platform_users.id"), nullable=False)
#     twitter_user_id = Column(String, unique=True, nullable=False)  # Twitter's internal user ID
#     username = Column(String, unique=True, nullable=False)  # @username
#     display_name = Column(String)
#     bio = Column(Text)
#     profile_image_url = Column(String)
#     verified = Column(Boolean, default=False)
#     followers_count = Column(Integer, default=0)
#     following_count = Column(Integer, default=0)
#     tweet_count = Column(Integer, default=0)
#     access_token = Column(String, nullable=False)
#     refresh_token = Column(String)
#     token_expires_at = Column(DateTime(timezone=True))
#     is_active = Column(Boolean, default=True)
#     created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
#     updated_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
#     
#     # Relationships
#     # platform_user = relationship("PlatformUser", back_populates="twitter_accounts")
#     # hashtag_campaigns = relationship("HashtagCampaign", back_populates="twitter_account")
#     # followers = relationship("TwitterFollower", back_populates="twitter_account")
#     # tweets = relationship("TwitterTweet", back_populates="twitter_account")
# 
# class HashtagCampaign(Base):
#     """Hashtags that organizations want to track."""
#     __tablename__ = "hashtag_campaigns"
#     
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     twitter_account_id = Column(UUID(as_uuid=True), ForeignKey("twitter_accounts.id"), nullable=False)
#     hashtag = Column(String, nullable=False)  # e.g., "#YourBrand"
#     name = Column(String, nullable=False)  # Campaign name
#     description = Column(Text)
#     is_active = Column(Boolean, default=True)
#     track_mentions = Column(Boolean, default=True)
#     track_sentiment = Column(Boolean, default=True)
#     alert_on_negative = Column(Boolean, default=True)
#     created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
#     updated_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
#     
#     # Relationships
#     # twitter_account = relationship("TwitterAccount", back_populates="hashtag_campaigns")
#     # mentions = relationship("HashtagMention", back_populates="campaign")
#     
#     # Composite unique constraint
#     # __table_args__ = (UniqueConstraint('twitter_account_id', 'hashtag', name='uq_hashtag_campaign'),)
# 
# class HashtagMention(Base):
#     """Individual mentions of tracked hashtags."""
#     __tablename__ = "hashtag_mentions"
#     
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     campaign_id = Column(UUID(as_uuid=True), ForeignKey("hashtag_campaigns.id"), nullable=False)
#     tweet_id = Column(String, nullable=False)  # Twitter's tweet ID
#     author_username = Column(String, nullable=False)
#     author_display_name = Column(String)
#     author_followers_count = Column(Integer)
#     author_verified = Column(Boolean, default=False)
#     tweet_text = Column(Text, nullable=False)
#     tweet_created_at = Column(DateTime(timezone=True), nullable=False)
#     likes_count = Column(Integer, default=0)
#     retweets_count = Column(Integer, default=0)
#     replies_count = Column(Integer, default=0)
#     sentiment_score = Column(Float)  # -1 to 1 (negative to positive)
#     sentiment_label = Column(String)  # "positive", "negative", "neutral"
#     location = Column(String)
#     language = Column(String)
#     collected_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
#     
#     # Relationships
#     # campaign = relationship("HashtagCampaign", back_populates="mentions")
#     
#     # Indexes for performance
#     # __table_args__ = (
#     #     Index('idx_hashtag_mentions_tweet_id', 'tweet_id'),
#     #     Index('idx_hashtag_mentions_author', 'author_username'),
#     #     Index('idx_hashtag_mentions_sentiment', 'sentiment_score'),
#     #     Index('idx_hashtag_mentions_created', 'tweet_created_at'),
#     # )
# 
# class TwitterFollower(Base):
#     """Follower data and growth tracking."""
#     __tablename__ = "twitter_followers"
#     
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     twitter_account_id = Column(UUID(as_uuid=True), ForeignKey("twitter_accounts.id"), nullable=False)
#     follower_username = Column(String, nullable=False)
#     follower_display_name = Column(String)
#     follower_bio = Column(Text)
#     follower_location = Column(String)
#     follower_verified = Column(Boolean, default=False)
#     follower_followers_count = Column(Integer)
#     follower_following_count = Column(Integer)
#     follower_tweet_count = Column(Integer)
#     follower_profile_image_url = Column(String)
#     followed_at = Column(DateTime(timezone=True), nullable=False)  # When they started following
#     is_active = Column(Boolean, default=True)  # Still following
#     unfollowed_at = Column(DateTime(timezone=True))  # When they unfollowed
#     collected_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
#     
#     # Relationships
#     # twitter_account = relationship("TwitterAccount", back_populates="followers")
#     
#     # Indexes for performance
#     # __table_args__ = (
#     #     Index('idx_twitter_followers_username', 'follower_username'),
#     #     Index('idx_twitter_followers_followed_at', 'followed_at'),
#     #     Index('idx_twitter_followers_active', 'is_active'),
#     # )
# 
# class TwitterTweet(Base):
#     """Tweet data and performance metrics."""
#     __tablename__ = "twitter_tweets"
#     
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     twitter_account_id = Column(UUID(as_uuid=True), ForeignKey("twitter_accounts.id"), nullable=False)
#     tweet_id = Column(String, unique=True, nullable=False)  # Twitter's tweet ID
#     tweet_text = Column(Text, nullable=False)
#     tweet_type = Column(String, default="tweet")  # tweet, retweet, reply, quote
#     in_reply_to_tweet_id = Column(String)  # If this is a reply
#     quoted_tweet_id = Column(String)  # If this quotes another tweet
#     retweeted_tweet_id = Column(String)  # If this is a retweet
#     hashtags = Column(JSON)  # Array of hashtags used
#     mentions = Column(JSON)  # Array of @mentions
#     urls = Column(JSON)  # Array of URLs in the tweet
#     media_urls = Column(JSON)  # Array of media URLs
#     tweet_created_at = Column(DateTime(timezone=True), nullable=False)
#     likes_count = Column(Integer, default=0)
#     retweets_count = Column(Integer, default=0)
#     replies_count = Column(Integer, default=0)
#     quote_count = Column(Integer, default=0)
#     bookmark_count = Column(Integer, default=0)
#     impression_count = Column(Integer, default=0)
#     engagement_rate = Column(Float)  # Calculated engagement rate
#     collected_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
#     updated_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
#     
#     # Relationships
#     # twitter_account = relationship("TwitterAccount", back_populates="tweets")
#     
#     # Indexes for performance
#     # __table_args__ = (
#     #     Index('idx_twitter_tweets_tweet_id', 'tweet_id'),
#     #     Index('idx_twitter_tweets_created', 'tweet_created_at'),
#     #     Index('idx_twitter_tweets_engagement', 'engagement_rate'),
#     #     Index('idx_twitter_tweets_type', 'tweet_type'),
#     # )
# 
# class TwitterAnalytics(Base):
#     """Aggregated Twitter analytics data."""
#     __tablename__ = "twitter_analytics"
#     
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     twitter_account_id = Column(UUID(as_uuid=True), ForeignKey("twitter_accounts.id"), nullable=False)
#     date = Column(Date, nullable=False)  # Analytics date
#     period = Column(String, default="daily")  # daily, weekly, monthly
#     
#     # Follower metrics
#     followers_count = Column(Integer, default=0)
#     followers_gained = Column(Integer, default=0)
#     followers_lost = Column(Integer, default=0)
#     net_followers = Column(Integer, default=0)
#     
#     # Tweet metrics
#     tweets_count = Column(Integer, default=0)
#     total_likes = Column(Integer, default=0)
#     total_retweets = Column(Integer, default=0)
#     total_replies = Column(Integer, default=0)
#     total_impressions = Column(Integer, default=0)
#     avg_engagement_rate = Column(Float, default=0.0)
#     
#     # Hashtag metrics
#     hashtags_tracked = Column(Integer, default=0)
#     hashtag_mentions = Column(Integer, default=0)
#     avg_sentiment_score = Column(Float, default=0.0)
#     
#     # Performance metrics
#     best_tweet_id = Column(String)
#     best_tweet_engagement = Column(Float)
#     peak_hour = Column(Integer)  # Hour of day with most engagement
#     peak_day = Column(Integer)   # Day of week with most engagement
#     
#     created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
#     
#     # Relationships
#     # twitter_account = relationship("TwitterAccount")
#     
#     # Composite unique constraint
#     # __table_args__ = (
#     #     UniqueConstraint('twitter_account_id', 'date', 'period', name='uq_twitter_analytics'),
#     #     Index('idx_twitter_analytics_date', 'date'),
#     #     Index('idx_twitter_analytics_period', 'period'),
#     # )
