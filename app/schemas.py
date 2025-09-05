from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from enum import Enum
import uuid
from decimal import Decimal

# ====================================================================================
# --- Enums: Defines fixed sets of choices for specific fields. ---
# ====================================================================================
class PlatformType(str, Enum):
    """
    An enum to categorize the type of application being tracked.
    - WEB2: Standard web applications.
    - WEB3: Blockchain-based applications.
    - BOTH: A hybrid of both Web2 and Web3 features.
    """
    WEB2 = "web2"
    WEB3 = "web3"
    BOTH = "both"

class SDKEventType(str, Enum):
    """
    An enum representing the types of events that can be sent from the client-side SDK.
    These mirror common analytics event types.
    - TRACK: A custom event for tracking a specific action.
    - PAGE: The user has viewed a new page.
    - SCREEN: The user has viewed a new screen (for mobile apps).
    - IDENTIFY: The user's identity has been set or updated.
    - GROUP: The user has been added to a group (e.g., a company).
    - ALIAS: An identifier is being linked to another (e.g., anonymousId to userId).
    - TX: A blockchain transaction event.
    """
    TRACK = "track"
    PAGE = "page"
    SCREEN = "screen"
    IDENTIFY = "identify"
    GROUP = "group"
    ALIAS = "alias"
    TX = "tx"
    
    # Add uppercase variants for backward compatibility
    TRACK_UPPER = "TRACK"
    PAGE_UPPER = "PAGE"
    SCREEN_UPPER = "SCREEN"
    IDENTIFY_UPPER = "IDENTIFY"
    GROUP_UPPER = "GROUP"
    ALIAS_UPPER = "ALIAS"
    TX_UPPER = "TX"

# ====================================================================================
# --- Common Schemas: Reusable data models for shared components. ---
# ====================================================================================
class Token(BaseModel):
    """
    A model for the JWT access token and its type.
    This is used for authentication responses.
    """
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """
    A model to hold the data decoded from a JWT access token.
    It includes the user's ID, email, and security scopes.
    """
    id: Optional[uuid.UUID] = None
    email: Optional[str] = None
    scopes: List[str] = []

# ====================================================================================
# --- PlatformUser Schemas: Models for users of your analytics dashboard. ---
# ====================================================================================
class PlatformUserBase(BaseModel):
    """
    The base schema for a PlatformUser, containing common fields.
    """
    email: EmailStr
    name: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False

class PlatformUserCreate(PlatformUserBase):
    """
    The schema for creating a new PlatformUser, including a password.
    This should only be used for the creation process.
    """
    password: str

class PlatformUserLogin(BaseModel):
    """
    The schema for a PlatformUser login request.
    """
    email: str
    password: str

class PasswordResetRequest(BaseModel):
    """
    Schema for requesting a password reset.
    """
    email: str

class PasswordResetConfirm(BaseModel):
    """
    Schema for confirming a password reset with token.
    """
    token: str
    new_password: str

class PasswordChange(BaseModel):
    """
    Schema for changing password when user is authenticated.
    """
    current_password: str
    new_password: str

class LoginAttempt(BaseModel):
    """Login attempt schema."""
    id: int
    email: str
    ip_address: str
    user_agent: str
    success: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class PlatformUser(BaseModel):
    """Platform user schema."""
    id: uuid.UUID
    email: str
    first_name: str = None
    last_name: str = None
    is_active: bool = True
    is_verified: bool = False
    role: str = "user"
    created_at: datetime
    last_login: datetime = None
    
    class Config:
        from_attributes = True

# ====================================================================================
# --- ClientCompany Schemas: Models for the companies using your SDK. ---
# ====================================================================================
class ClientCompanyBase(BaseModel):
    """
    The base schema for a ClientCompany.
    """
    name: str

class ClientCompanyRegisterInput(ClientCompanyBase):
    """
    Schema for the input when a PlatformUser registers a new ClientCompany.
    """
    pass

class ClientCompanyCreateResponse(ClientCompanyBase):
    """
    The response schema for a newly created ClientCompany.
    Crucially, it includes the one-time-return `api_key`.
    """
    id: uuid.UUID
    platform_user_id: uuid.UUID
    created_at: datetime
    is_active: bool
    api_key: str  # Only returned on creation

    class Config:
        from_attributes = True

class ClientCompanyRegenerateAPIKeyResponse(ClientCompanyCreateResponse):
    """
    Schema for the one-time return of a newly regenerated API key.
    This inherits from the creation response as it's a similar process.
    """
    api_key: str

class ClientCompanyUpdate(BaseModel):
    """
    Schema for updating an existing client company's details.
    All fields are optional to allow for partial updates.
    """
    name: Optional[str] = None

    class Config:
        extra = "ignore"
        
class ClientCompany(ClientCompanyBase):
    """
    The complete schema for a ClientCompany, as retrieved from the database.
    This schema does NOT include the raw `api_key` for security reasons.
    """
    id: uuid.UUID
    platform_user_id: uuid.UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# ====================================================================================
# --- ClientAppUser Schemas: Models for the users of your clients' applications. ---
# ====================================================================================
class ClientAppUserBase(BaseModel):
    """
    The base schema for a user of a client's application.
    Includes fields for both Web2 and Web3 users.
    """
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    country: Optional[str] = Field(None, max_length=2)
    is_verified: bool = False
    subscription_plan: str = "free"
    billing_id: Optional[str] = None
    wallet_address: Optional[str] = None
    wallet_type: Optional[str] = None

class ClientAppUserCreate(ClientAppUserBase):
    """
    Schema for creating a new ClientAppUser.
    """
    password: str

class ClientAppUser(ClientAppUserBase):
    """
    The complete schema for a ClientAppUser, as retrieved from the database.
    """
    id: uuid.UUID
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True

# ====================================================================================
# --- Event Schemas: Models for tracking events from the SDK. ---
# ====================================================================================
class EventBase(BaseModel):
    """
    The base schema for a standard event.
    """
    event_name: str
    event_type: SDKEventType
    user_id: Optional[str] = None
    anonymous_id: Optional[str] = None
    session_id: Optional[str] = None
    properties: Dict[str, Any] = {}

class Event(EventBase):
    """
    The complete schema for a processed Event, as it will be stored in the database.
    """
    id: uuid.UUID
    client_company_id: uuid.UUID
    timestamp: datetime
    event_type: Union[SDKEventType, str]  # Allow both enum and string values

    @validator('event_type', pre=True)
    def normalize_event_type(cls, v):
        """Normalize event type to handle both uppercase and lowercase values."""
        if isinstance(v, str):
            # Convert to lowercase to match enum values
            return v.lower()
        return v

    class Config:
        from_attributes = True

class Web3EventBase(BaseModel):
    """
    The base schema for a Web3-specific event.
    Note that `user_id` and `wallet_address` are mandatory here.
    """
    user_id: str
    event_name: str
    wallet_address: str
    chain_id: str
    transaction_hash: Optional[str] = None
    contract_address: Optional[str] = None
    properties: Dict[str, Any] = {}

class Web3Event(Web3EventBase):
    """
    The complete schema for a processed Web3Event, as it will be stored in the database.
    """
    id: uuid.UUID
    client_company_id: uuid.UUID
    timestamp: datetime

    class Config:
        from_attributes = True

class SDKEventPayload(BaseModel):
    """
    The main schema for the JSON payload received from the client-side SDK.
    This is a flexible schema that can handle various event types and Web3 fields.
    All fields are now optional to prevent validation errors from malformed payloads.
    """
    type: Optional[Union[SDKEventType, str]] = None
    eventName: Optional[str] = None
    user_id: Optional[str] = None
    anonymous_id: Optional[str] = None
    session_id: Optional[str] = None
    properties: Dict[str, Any] = {}
    timestamp: Optional[Union[datetime, str]] = None

    # Optional Web3-specific fields that are included in the payload
    wallet_address: Optional[str] = None
    chain_id: Optional[str] = None
    transaction_hash: Optional[str] = None
    contract_address: Optional[str] = None

    # Region tracking fields
    country: Optional[str] = Field(None, description="ISO 3166-1 alpha-2 country code (e.g., 'US', 'CA')", example="US", max_length=2)
    region: Optional[str] = Field(None, description="State/province/region name", example="California", max_length=100)
    city: Optional[str] = Field(None, description="City name", example="San Francisco", max_length=100)
    ip_address: Optional[str] = Field(None, description="IPv4 or IPv6 address", example="192.168.1.1", max_length=45)

    @validator('type', pre=True, always=True)
    def ensure_valid_event_type(cls, v):
        """
        Validates the event type. If it's not a recognized enum value or is missing,
        it defaults to 'track'. This prevents the SDK from failing on a bad event type.
        """
        if v and v.upper() in SDKEventType.__members__:
            return SDKEventType[v.upper()]
        return SDKEventType.TRACK
    
    @validator('country', pre=True)
    def validate_country(cls, v):
        """Validate and clean country field."""
        if v is None:
            return None
        
        # Convert to string and strip whitespace
        v_str = str(v).strip()
        
        # Handle common Swagger UI defaults and invalid values
        if v_str.lower() in ['string', 'example', 'test', 'none', 'null', 'undefined', '']:
            return None
        
        # Check length constraint
        if len(v_str) > 2:
            return None  # Reset invalid values to None
        
        # Convert to uppercase for consistency
        return v_str.upper() if v_str else None
    
    @validator('region', 'city')
    def validate_region_city(cls, v):
        """Validate and clean region and city fields."""
        if v is None:
            return None
        
        # Convert to string and strip whitespace
        v_str = str(v).strip()
        
        # Handle common Swagger UI defaults and invalid values
        if v_str.lower() in ['string', 'example', 'test', 'none', 'null', 'undefined', '']:
            return None
        
        # Check length constraint
        if len(v_str) > 100:
            return None  # Reset invalid values to None
        
        # Return cleaned string or None
        return v_str if v_str else None
    
    @validator('chain_id', 'contract_address', pre=True)
    def validate_optional_string_fields(cls, v):
        """Validate and clean optional string fields."""
        if v is None:
            return None
        
        # Convert to string and strip whitespace
        v_str = str(v).strip()
        
        # Handle common Swagger UI defaults and invalid values
        if v_str.lower() in ['string', 'example', 'test', 'none', 'null', 'undefined', '']:
            return None
        
        # Return cleaned string or None
        return v_str if v_str else None


# ====================================================================================
# --- Metrics Schemas: Models for aggregated analytics and dashboard data. ---
# ====================================================================================
class MetricsBase(BaseModel):
    """
    A base model for displaying an individual metric on a dashboard.
    This was the missing class that caused the initial ImportError.
    """
    name: str = Field(..., description="The name of the metric.")
    value: Union[float, int, str] = Field(..., description="The value of the metric.")
    timestamp: datetime = Field(..., description="The timestamp when the metric was calculated.")

class MetricsCreate(BaseModel):
    """
    The schema for creating a new `PlatformMetrics` record.
    It includes various metrics for both Web2 and Web3 applications.
    """
    total_users: int = 0
    active_sessions: int = 0
    conversion_rate: float = 0.0
    revenue_usd: float = 0.0
    total_value_locked: float = 0.0
    active_wallets: int = 0
    transaction_volume_24h: float = 0.0
    new_contracts: int = 0
    daily_page_views: int = 0
    sales_count: int = 0
    platform: PlatformType = PlatformType.BOTH
    source: Optional[str] = None
    chain_id: Optional[str] = None
    contract_address: Optional[str] = None
    
    # Region tracking fields
    country: Optional[str] = Field(None, description="ISO 3166-1 alpha-2 country code (e.g., 'US', 'CA')", example="US", max_length=2)
    region: Optional[str] = Field(None, description="State/province/region name", example="California", max_length=100)
    city: Optional[str] = Field(None, description="City name", example="San Francisco", max_length=100)
    
    @validator('country', pre=True)
    def validate_country(cls, v):
        """Validate and clean country field."""
        if v is None:
            return None
        
        # Convert to string and strip whitespace
        v_str = str(v).strip()
        
        # Handle common Swagger UI defaults and invalid values
        if v_str.lower() in ['string', 'example', 'test', 'none', 'null', 'undefined', '']:
            return None
        
        # Check length constraint
        if len(v_str) > 2:
            return None  # Reset invalid values to None
        
        # Convert to uppercase for consistency
        return v_str.upper() if v_str else None
    
    @validator('region', 'city', pre=True)
    def validate_region_city(cls, v):
        """Validate and clean region and city fields."""
        if v is None:
            return None
        
        # Convert to string and strip whitespace
        v_str = str(v).strip()
        
        # Handle common Swagger UI defaults and invalid values
        if v_str.lower() in ['string', 'example', 'test', 'none', 'null', 'undefined', '']:
            return None
        
        # Check length constraint
        if len(v_str) > 100:
            return None  # Reset invalid values to None
        
        # Return cleaned string or None
        return v_str if v_str else None
    
    @validator('source', pre=True)
    def validate_source(cls, v):
        """Validate and clean source field."""
        if v is None:
            return None
        
        # Convert to string and strip whitespace
        v_str = str(v).strip()
        
        # Handle common Swagger UI defaults and invalid values
        if v_str.lower() in ['string', 'example', 'test', 'none', 'null', 'undefined', '']:
            return None
        
        # Return cleaned string or None
        return v_str if v_str else None

class PlatformMetrics(MetricsCreate):
    """
    The complete schema for a PlatformMetrics record, as retrieved from the database.
    """
    id: uuid.UUID
    timestamp: datetime
    client_company_id: uuid.UUID

    class Config:
        from_attributes = True

class TimeSeriesDataPoint(BaseModel):
    """
    A single data point for a time series chart.
    """
    timestamp: datetime
    value: Union[float, int]

class MetricsResponse(BaseModel):
    """
    The response schema for a metrics endpoint,
    containing both key metrics and optional time-series data.
    """
    key_metrics: List[MetricsBase] = Field(..., description="A list of key metrics for display.")
    time_series: Optional[Dict[str, List[TimeSeriesDataPoint]]] = Field(
        None,
        description="Optional dictionary of time-series data, where keys are metric names."
    )


# ====================================================================================
# --- Region Analytics Schemas: Models for location-based analytics. ---
# ====================================================================================
class RegionData(BaseModel):
    """
    A model representing geographic data for analytics.
    """
    country: str = Field(..., description="ISO 3166-1 alpha-2 country code")
    region: Optional[str] = Field(None, description="State/province/region name")
    city: Optional[str] = Field(None, description="City name")
    user_count: int = Field(..., description="Number of users from this region")
    event_count: int = Field(..., description="Number of events from this region")
    conversion_rate: Optional[float] = Field(None, description="Conversion rate for this region")
    revenue_usd: Optional[float] = Field(None, description="Revenue from this region")

class RegionAnalyticsResponse(BaseModel):
    """
    Response schema for region-based analytics.
    """
    regions: List[Dict[str, Union[str, int, None]]] = Field(..., description="List of regions with country and events count")
    total_users: int = Field(..., description="Total users across all regions")
    total_events: int = Field(..., description="Total events across all regions")
    top_countries: List[Dict[str, Union[str, int, None]]] = Field(..., description="Top countries with country and events count")
    top_cities: List[Dict[str, Union[str, int, None]]] = Field(..., description="Top cities with city and events count")

class UserLocationData(BaseModel):
    """
    Schema for user location information.
    """
    user_id: str = Field(..., description="User identifier")
    country: Optional[str] = Field(None, description="ISO 3166-1 alpha-2 country code")
    region: Optional[str] = Field(None, description="State/province/region name")
    city: Optional[str] = Field(None, description="City name")
    ip_address: Optional[str] = Field(None, description="User's IP address")
    last_seen: datetime = Field(..., description="Last time user was active")

# ====================================================================================
# --- CSV Import Schemas: Models for importing wallet and user data. ---
# ====================================================================================
class ImportResult(BaseModel):
    """
    Response schema for CSV import operations.
    """
    success: bool = Field(..., description="Whether the import was successful")
    imported_count: int = Field(..., description="Number of records successfully imported")
    updated_count: int = Field(..., description="Number of existing records updated")
    total_rows: int = Field(..., description="Total number of rows processed")
    errors: List[str] = Field(default=[], description="List of error messages for failed rows")

class ImportTemplate(BaseModel):
    """
    Schema for CSV import template structure.
    """
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    columns: List[str] = Field(..., description="Required column names")
    optional_columns: List[str] = Field(default=[], description="Optional column names")
    example_data: List[Dict[str, str]] = Field(..., description="Example data rows")

class ImportTemplates(BaseModel):
    """
    Response schema containing all available import templates.
    """
    templates: List[ImportTemplate] = Field(..., description="Available import templates")
    instructions: str = Field(..., description="General import instructions")


# ====================================================================================
# --- Unique Users Analytics Schemas: Models for user analytics. ---
# ====================================================================================
class UniqueUserData(BaseModel):
    """
    Schema for unique user analytics data.
    """
    session_id: str = Field(..., description="Unique session identifier")
    first_seen: datetime = Field(..., description="First time this user was seen")
    last_seen: datetime = Field(..., description="Last time this user was seen")
    total_events: int = Field(..., description="Total number of events from this user")
    company_id: Optional[uuid.UUID] = Field(None, description="Company ID if filtered")
    company_name: Optional[str] = Field(None, description="Company name if filtered")

class UniqueUsersResponse(BaseModel):
    """
    Response schema for unique users analytics.
    """
    total_unique_users: int = Field(..., description="Total number of unique users (sessions)")
    total_events: int = Field(..., description="Total number of events")
    avg_events_per_user: float = Field(..., description="Average events per user")
    users_per_day: List[Dict[str, Union[str, int]]] = Field(..., description="Daily user counts")
    recent_users: List[UniqueUserData] = Field(..., description="Most recent users")
    top_users_by_events: List[UniqueUserData] = Field(..., description="Users with most events")


# Twitter Integration Schemas
class CompanyTwitterBase(BaseModel):
    """Base company Twitter schema."""
    twitter_handle: str
    description: str = None


class CompanyTwitterCreate(CompanyTwitterBase):
    """Create company Twitter account schema."""
    company_id: str  # UUID as string


class CompanyTwitterUpdate(BaseModel):
    """Update company Twitter account schema."""
    description: str = None


class CompanyTwitterResponse(CompanyTwitterBase):
    """Company Twitter account response schema."""
    id: str  # UUID as string
    company_id: str  # UUID as string
    twitter_user_id: str | None = None
    followers_count: int
    following_count: int
    tweets_count: int
    profile_image_url: str | None = None
    verified: bool
    last_updated: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True


class TwitterTweetBase(BaseModel):
    """Base Twitter tweet schema."""
    tweet_id: str
    text: str
    created_at: datetime
    retweet_count: int = 0
    like_count: int = 0
    reply_count: int = 0
    quote_count: int = 0


class TwitterTweetResponse(TwitterTweetBase):
    """Twitter tweet response schema."""
    id: str  # UUID as string
    company_twitter_id: str  # UUID as string
    hashtags: list = None
    mentions: list = None
    sentiment_score: float = None
    sentiment_label: str = None
    collected_at: datetime
    
    class Config:
        from_attributes = True


class TwitterFollowerBase(BaseModel):
    """Base Twitter follower schema."""
    follower_id: str
    username: str
    display_name: str = None
    verified: bool = False
    followers_count: int = 0
    following_count: int = 0
    tweets_count: int = 0


class TwitterFollowerResponse(TwitterFollowerBase):
    """Twitter follower response schema."""
    id: str  # UUID as string
    company_twitter_id: str  # UUID as string
    profile_image_url: str = None
    followed_at: datetime = None
    collected_at: datetime
    
    class Config:
        from_attributes = True


class TwitterAnalyticsBase(BaseModel):
    """Base Twitter analytics schema."""
    date: date
    total_tweets: int = 0
    total_likes: int = 0
    total_retweets: int = 0
    total_replies: int = 0
    total_mentions: int = 0
    followers_gained: int = 0
    followers_lost: int = 0
    engagement_rate: float = 0.0
    reach_estimate: int = 0


class TwitterAnalyticsResponse(TwitterAnalyticsBase):
    """Twitter analytics response schema."""
    id: str  # UUID as string
    company_twitter_id: str  # UUID as string
    created_at: datetime
    
    class Config:
        from_attributes = True


class TwitterProfileData(BaseModel):
    """Twitter profile data from API."""
    id: str
    username: str
    name: str
    description: str = None
    profile_image_url: str = None
    verified: bool = False
    followers_count: int
    following_count: int
    tweets_count: int
    created_at: datetime = None


class TwitterSyncRequest(BaseModel):
    """Request to sync Twitter data."""
    company_id: str  # UUID as string
    twitter_handle: str
    sync_tweets: bool = True
    sync_followers: bool = True
    max_tweets: int = 100
    max_followers: int = 1000


class TwitterSyncResponse(BaseModel):
    """Twitter sync response."""
    success: bool
    message: str
    profile_updated: bool = False
    tweets_synced: int = 0
    followers_synced: int = 0
    errors: List[str] = []


# New Mention-related Schemas
class MentionBase(BaseModel):
    """Base mention schema."""
    tweet_id: str
    username: str
    text: str
    created_at: datetime
    retweet_count: int = 0
    like_count: int = 0
    reply_count: int = 0


class MentionResponse(MentionBase):
    """Mention response schema."""
    id: str  # UUID as string
    company_twitter_id: str  # UUID as string
    sentiment_score: float = None
    sentiment_label: str = None
    collected_at: datetime
    
    class Config:
        from_attributes = True


class MentionAnalyticsBase(BaseModel):
    """Base mention analytics schema."""
    start_date: date
    end_date: date
    total_mentions: int = 0
    total_likes: int = 0
    total_retweets: int = 0
    total_replies: int = 0


class MentionAnalyticsResponse(MentionAnalyticsBase):
    """Mention analytics response schema."""
    mentions_by_date: Dict[str, Dict[str, int]] = {}
    date_range: Dict[str, date] = {}
    
    class Config:
        from_attributes = True


class MentionSearchRequest(BaseModel):
    """Request to search for mentions."""
    company_id: str  # UUID as string
    twitter_handle: str = None
    start_date: datetime = None
    end_date: datetime = None
    limit: int = 100
    include_sentiment: bool = False


class MentionNotificationRequest(BaseModel):
    """Request to set up mention notifications."""
    company_id: str  # UUID as string
    twitter_handle: str
    notification_email: str = None
    notification_webhook: str = None
    mention_keywords: List[str] = []
    is_active: bool = True


# Twitter User Autocomplete Schemas
class TwitterUserSuggestion(BaseModel):
    """Twitter user suggestion for autocomplete."""
    id: str
    username: str
    name: str
    description: str = ""
    profile_image_url: str = None
    verified: bool = False
    followers_count: int = 0
    following_count: int = 0
    tweets_count: int = 0
    created_at: str = None
    display_name: str
    verified_badge: str = ""


class TwitterHandleValidationRequest(BaseModel):
    """Request to validate a Twitter handle."""
    handle: str


class TwitterHandleValidationResponse(BaseModel):
    """Response for Twitter handle validation."""
    valid: bool
    handle: str
    error: str = None
    user_data: Optional[TwitterProfileData] = None
    suggestions: List[TwitterUserSuggestion] = []


class TwitterUserSearchRequest(BaseModel):
    """Request to search for Twitter users."""
    query: str
    max_results: int = 5


class TwitterUserSearchResponse(BaseModel):
    """Response for Twitter user search."""
    users: List[TwitterUserSuggestion]
    query: str
    total_results: int

# Hashtag Mention schemas
class HashtagMentionBase(BaseModel):
    """Base hashtag mention schema."""
    hashtag: str
    tweet_id: str
    username: str
    text: str
    created_at: datetime
    engagement: int = 0


class HashtagMentionResponse(HashtagMentionBase):
    """Hashtag mention response schema."""
    id: str  # UUID as string
    company_id: str  # UUID as string
    collected_at: datetime
    
    class Config:
        from_attributes = True

# Hashtag Search schemas
class HashtagSearchRequest(BaseModel):
    """Request to search for tweets with a hashtag."""
    hashtag: str = Field(..., description="Hashtag to search for (with or without #)")
    max_results: int = Field(10, ge=10, le=100, description="Maximum number of results (10-100 for Twitter API v2)")


class HashtagSearchResponse(BaseModel):
    """Response for hashtag search."""
    hashtag: str
    results_count: int
    tweets: List[Dict[str, Any]]

# ====================================================================================
# --- Data Aggregation Schemas ---
# ====================================================================================

class SubscriptionPlanBase(BaseModel):
    """Base subscription plan schema."""
    plan_name: str = Field(..., description="Plan name: basic, pro, or enterprise")
    plan_tier: int = Field(..., ge=1, le=3, description="Plan tier: 1=basic, 2=pro, 3=enterprise")
    raw_data_retention_days: int = Field(0, ge=0, description="Days to retain raw data (0 = no raw data)")
    aggregation_frequency: str = Field("daily", description="Aggregation frequency: daily, hourly, real_time")
    max_raw_events_per_month: int = Field(0, ge=0, description="Maximum raw events per month")
    max_aggregated_rows_per_month: int = Field(100000, ge=1000, description="Maximum aggregated rows per month")
    monthly_price_usd: float = Field(0.0, ge=0.0, description="Monthly price in USD")

class SubscriptionPlanCreate(SubscriptionPlanBase):
    """Schema for creating a subscription plan."""
    pass

class SubscriptionPlanUpdate(BaseModel):
    """Schema for updating a subscription plan."""
    plan_name: Optional[str] = None
    plan_tier: Optional[int] = Field(None, ge=1, le=3)
    raw_data_retention_days: Optional[int] = Field(None, ge=0)
    aggregation_frequency: Optional[str] = None
    max_raw_events_per_month: Optional[int] = Field(None, ge=0)
    max_aggregated_rows_per_month: Optional[int] = Field(None, ge=1000)
    monthly_price_usd: Optional[float] = Field(None, ge=0.0)

class SubscriptionPlanResponse(SubscriptionPlanBase):
    """Schema for subscription plan response."""
    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RawEventBase(BaseModel):
    """Base raw event schema."""
    campaign_id: str = Field(..., description="Campaign identifier")
    event_name: str = Field(..., description="Event name")
    event_type: str = Field(..., description="Event type")
    user_id: Optional[str] = None
    anonymous_id: Optional[str] = None
    session_id: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    ip_address: Optional[str] = None
    event_timestamp: datetime = Field(..., description="When the event occurred")

class RawEventCreate(RawEventBase):
    """Schema for creating a raw event."""
    pass

class RawEventResponse(RawEventBase):
    """Schema for raw event response."""
    id: uuid.UUID
    company_id: uuid.UUID
    received_at: datetime

    class Config:
        from_attributes = True


class CampaignAnalyticsDailyBase(BaseModel):
    """Base daily analytics schema."""
    campaign_id: str = Field(..., description="Campaign identifier")
    analytics_date: date = Field(..., description="Analytics date")
    event_counts: Dict[str, int] = Field(default_factory=dict)
    country_breakdown: Dict[str, int] = Field(default_factory=dict)
    region_breakdown: Dict[str, int] = Field(default_factory=dict)
    city_breakdown: Dict[str, int] = Field(default_factory=dict)
    unique_users: int = Field(0, ge=0)
    new_users: int = Field(0, ge=0)
    returning_users: int = Field(0, ge=0)
    conversion_rate: float = Field(0.0, ge=0.0, le=1.0)
    campaign_revenue_usd: float = Field(0.0, ge=0.0)

class CampaignAnalyticsDailyCreate(CampaignAnalyticsDailyBase):
    """Schema for creating daily analytics."""
    pass

class CampaignAnalyticsDailyResponse(CampaignAnalyticsDailyBase):
    """Schema for daily analytics response."""
    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CampaignAnalyticsHourlyBase(BaseModel):
    """Base hourly analytics schema."""
    campaign_id: str = Field(..., description="Campaign identifier")
    analytics_date: date = Field(..., description="Analytics date")
    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    event_counts: Dict[str, int] = Field(default_factory=dict)
    country_breakdown: Dict[str, int] = Field(default_factory=dict)
    region_breakdown: Dict[str, int] = Field(default_factory=dict)
    city_breakdown: Dict[str, int] = Field(default_factory=dict)
    unique_users: int = Field(0, ge=0)
    new_users: int = Field(0, ge=0)
    returning_users: int = Field(0, ge=0)
    conversion_rate: float = Field(0.0, ge=0.0, le=1.0)
    campaign_revenue_usd: float = Field(0.0, ge=0.0)

class CampaignAnalyticsHourlyCreate(CampaignAnalyticsHourlyBase):
    """Schema for creating hourly analytics."""
    pass

class CampaignAnalyticsHourlyResponse(CampaignAnalyticsHourlyBase):
    """Schema for hourly analytics response."""
    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AggregationRequest(BaseModel):
    """Request to trigger data aggregation."""
    company_id: uuid.UUID
    campaign_id: str
    start_date: date
    end_date: date
    force_reaggregate: bool = Field(False, description="Force re-aggregation of existing data")


class AggregationResponse(BaseModel):
    """Response from data aggregation."""
    company_id: uuid.UUID
    campaign_id: str
    start_date: date
    end_date: date
    raw_events_processed: int
    daily_aggregations_created: int
    hourly_aggregations_created: int
    storage_saved_mb: float
    processing_time_seconds: float
    message: str
