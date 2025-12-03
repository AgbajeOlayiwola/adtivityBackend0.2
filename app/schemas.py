from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field, validator, root_validator
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
    - PAYMENT_STARTED: A payment process has been initiated.
    - PAYMENT_COMPLETED: A payment has been successfully completed.
    - PAYMENT_FAILED: A payment has failed.
    - PAYMENT_CANCELLED: A payment has been cancelled.
    """
    TRACK = "track"
    PAGE = "page"
    SCREEN = "screen"
    IDENTIFY = "identify"
    GROUP = "group"
    ALIAS = "alias"
    TX = "tx"
    PAYMENT_STARTED = "payment_started"
    PAYMENT_COMPLETED = "payment_completed"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_CANCELLED = "payment_cancelled"
    
    # Add uppercase variants for backward compatibility
    TRACK_UPPER = "TRACK"
    PAGE_UPPER = "PAGE"
    SCREEN_UPPER = "SCREEN"
    IDENTIFY_UPPER = "IDENTIFY"
    GROUP_UPPER = "GROUP"
    ALIAS_UPPER = "ALIAS"
    TX_UPPER = "TX"
    PAYMENT_STARTED_UPPER = "PAYMENT_STARTED"
    PAYMENT_COMPLETED_UPPER = "PAYMENT_COMPLETED"
    PAYMENT_FAILED_UPPER = "PAYMENT_FAILED"
    PAYMENT_CANCELLED_UPPER = "PAYMENT_CANCELLED"

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
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    role: str = "user"
    created_at: datetime
    last_login: Optional[datetime] = None
    
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
    campaign_url: Optional[str] = Field(None, description="Optional URL for the company's campaign")
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
    campaign_url: Optional[str] = None

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
    is_twitter_added: Optional[bool] = None

    class Config:
        extra = "ignore"

class TwitterStatusUpdate(BaseModel):
    """
    Schema for updating Twitter integration status.
    """
    is_twitter_added: bool = Field(..., description="Whether Twitter integration has been added")

class UserProfileResponse(BaseModel):
    """
    Enhanced user profile response that includes Twitter status information.
    """
    id: uuid.UUID
    email: str
    name: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    companies: List[ClientCompany] = []
    has_twitter_integration: bool = False  # True if any company has Twitter added
    total_companies: int = 0
    companies_with_twitter: int = 0
    twitter_profile: Optional[CompanyTwitterResponse] = None  # Single Twitter profile for user's company
        
class ClientCompany(ClientCompanyBase):
    """
    The complete schema for a ClientCompany, as retrieved from the database.
    This schema does NOT include the raw `api_key` for security reasons.
    """
    id: uuid.UUID
    platform_user_id: uuid.UUID
    is_active: bool
    is_twitter_added: bool = False
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
    company_id: Optional[uuid.UUID] = None  # Alias for client_company_id for convenience
    timestamp: datetime
    event_type: Union[SDKEventType, str]  # Allow both enum and string values

    @validator('event_type', pre=True)
    def normalize_event_type(cls, v):
        """Normalize event type to handle both uppercase and lowercase values."""
        if isinstance(v, str):
            # Convert to lowercase to match enum values
            return v.lower()
        return v
    
    @root_validator(skip_on_failure=True)
    def set_company_id(cls, values):
        """Set company_id from client_company_id if not provided."""
        # Always set company_id from client_company_id if it exists
        if 'client_company_id' in values and values.get('client_company_id') is not None:
            values['company_id'] = values['client_company_id']
        return values

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
    chain_id: Optional[str] = None  # Made optional for flexibility
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


class CompanyTwitterPatch(BaseModel):
    """PATCH update schema for Twitter account - allows partial updates including twitter_handle and twitter_user_id."""
    twitter_handle: Optional[str] = None
    twitter_user_id: Optional[str] = None
    description: Optional[str] = None


class CompanyTwitterResponse(CompanyTwitterBase):
    """Company Twitter account response schema."""
    id: str  # UUID as string
    company_id: str  # UUID as string
    twitter_user_id: Optional[str] = None
    followers_count: int
    following_count: int
    tweets_count: int
    profile_image_url: Optional[str] = None
    verified: bool
    last_updated: datetime
    
    @classmethod
    def from_orm(cls, obj):
        """Convert ORM object to response schema, handling UUID conversion."""
        data = {
            'id': str(obj.id),
            'company_id': str(obj.company_id),
            'twitter_handle': obj.twitter_handle,
            'description': obj.description,
            'twitter_user_id': str(obj.twitter_user_id) if obj.twitter_user_id else None,
            'followers_count': obj.followers_count,
            'following_count': obj.following_count,
            'tweets_count': obj.tweets_count,
            'profile_image_url': obj.profile_image_url,
            'verified': obj.verified,
            'last_updated': obj.last_updated
        }
        return cls(**data)
    
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
    hashtags: List[str] = Field(default_factory=list)
    mentions: List[str] = Field(default_factory=list)


class TwitterTweetResponse(TwitterTweetBase):
    """Twitter tweet response schema."""
    id: str  # UUID as string
    company_twitter_id: str  # UUID as string
    hashtags: Optional[list] = None
    mentions: Optional[list] = None
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    collected_at: Optional[datetime] = None
    
    @classmethod
    def from_orm(cls, obj):
        """Convert ORM object to response schema with UUID to string conversion."""
        data = {
            'id': str(obj.id),
            'tweet_id': obj.tweet_id,
            'company_twitter_id': str(obj.company_twitter_id),
            'text': obj.text,
            'created_at': obj.created_at,
            'retweet_count': obj.retweet_count,
            'like_count': obj.like_count,
            'reply_count': obj.reply_count,
            'quote_count': obj.quote_count,
            'hashtags': obj.hashtags or [],
            'mentions': obj.mentions or [],
            'sentiment_score': getattr(obj, 'sentiment_score', None),
            'sentiment_label': getattr(obj, 'sentiment_label', None),
            'collected_at': obj.collected_at
        }
        return cls(**data)
    
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


class TwitterAnalyticsDashboardResponse(BaseModel):
    """Twitter analytics response for dashboard frontend."""
    total_mentions: int = 0
    total_likes: int = 0
    total_followers: int = 0
    mentions_by_date: List[Dict[str, Any]] = []
    engagement_by_type: List[Dict[str, Any]] = []
    top_topics: List[Dict[str, Any]] = []
    
    class Config:
        from_attributes = True


class TwitterProfileData(BaseModel):
    """Twitter profile data from API."""
    id: Optional[str] = None
    username: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    profile_image_url: Optional[str] = None
    verified: bool = False
    followers_count: int = 0
    following_count: int = 0
    tweets_count: int = 0
    created_at: Optional[datetime] = None


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


# KOL Analysis Schemas
class KOLAnalysisRequest(BaseModel):
    """Request for KOL (Key Opinion Leader) analysis."""
    username: str = Field(..., description="Twitter username to analyze (with or without @)")
    max_tweets: int = Field(100, ge=10, le=100, description="Maximum number of user's tweets to fetch for engagement analysis")
    max_mentions: int = Field(100, ge=10, le=100, description="Maximum number of mentions to fetch")


class KOLTweetData(BaseModel):
    """Tweet data for KOL analysis."""
    tweet_id: str
    text: str
    created_at: str
    author_username: Optional[str] = None
    author_name: Optional[str] = None
    author_verified: bool = False
    retweet_count: int = 0
    like_count: int = 0
    reply_count: int = 0
    quote_count: int = 0
    hashtags: List[str] = []
    mentions: List[str] = []


class KOLAnalysisResponse(BaseModel):
    """Response for KOL analysis - no data is saved to database."""
    username: str
    profile: TwitterProfileData
    user_tweets: List[KOLTweetData] = []  # User's own tweets with engagement metrics
    mentions: List[KOLTweetData] = []  # Tweets that mention the user
    analysis_summary: Dict[str, Any] = {}
    error: Optional[str] = None


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


# Web3 Analytics Schemas
class Web3WalletActivity(BaseModel):
    """Web3 wallet activity data."""
    wallet_address: str
    total_events: int
    unique_chains: int
    first_seen: str
    last_seen: str


class Web3ChainData(BaseModel):
    """Web3 chain analytics data."""
    chain_id: str
    total_events: int
    unique_wallets: int
    unique_users: int
    first_event: Optional[str] = None
    last_event: Optional[str] = None
    avg_events_per_wallet: float


class Web3TransactionData(BaseModel):
    """Web3 transaction analytics data."""
    transaction_hash: Optional[str] = None
    wallet_address: str
    contract_address: Optional[str] = None
    chain_id: str
    event_name: str
    timestamp: str


class Web3UserJourney(BaseModel):
    """Web3 user journey data."""
    user_id: str
    wallet_address: str
    total_events: int
    chains_used: List[str]
    contracts_interacted: List[str]
    first_activity: str
    last_activity: str
    activity_duration_days: int
    events: List[Dict[str, Any]]


class Web3AnalyticsSummary(BaseModel):
    """Web3 analytics summary data."""
    total_events: int
    total_wallets: int
    total_chains: int
    total_contracts: int
    active_users: int
    growth_metrics: Dict[str, Any]
    top_chains: List[Dict[str, Any]]
    top_contracts: List[Dict[str, Any]]
    period: Dict[str, Any]


# Web3 Monitoring Schemas
class Web3WalletMonitoring(BaseModel):
    """Web3 wallet monitoring data."""
    wallet_address: str
    total_interactions: int
    total_amount: float
    unique_contracts: List[str]
    chains_used: List[str]
    interaction_history: List[Dict[str, Any]]
    contract_details: List[Dict[str, Any]]
    summary: Dict[str, Any]


class Web3ContractMonitoring(BaseModel):
    """Web3 contract monitoring data."""
    contract_address: str
    total_interactions: int
    unique_wallets: int
    total_amount: float
    chains_used: List[str]
    wallet_interactions: List[Dict[str, Any]]
    summary: Dict[str, Any]


class Web3InteractionDetail(BaseModel):
    """Web3 interaction detail data."""
    transaction_hash: Optional[str] = None
    contract_address: Optional[str] = None
    chain_id: str
    event_name: str
    amount: float
    token_symbol: Optional[str] = None
    timestamp: str
    properties: Dict[str, Any]
    user_id: str


class Web3WalletActivity(BaseModel):
    """Web3 wallet activity data."""
    wallet_address: str
    total_interactions: int
    total_amount: float
    chains_used: List[str]
    event_types: List[str]
    first_interaction: str
    last_interaction: str
    recent_interactions: List[Dict[str, Any]]


# ====================================================================================
# --- Wallet Connection Schemas ---
# ====================================================================================

class WalletConnectionBase(BaseModel):
    """Base wallet connection schema."""
    wallet_address: str
    wallet_type: str  # 'metamask', 'solflare', 'phantom', etc.
    network: str  # 'ethereum', 'solana', 'polygon', etc.
    wallet_name: Optional[str] = None


class WalletConnectionCreate(WalletConnectionBase):
    """Schema for creating a wallet connection."""
    company_id: uuid.UUID
    verification_signature: Optional[str] = None  # For wallet verification


class WalletConnectionUpdate(BaseModel):
    """Schema for updating a wallet connection."""
    wallet_name: Optional[str] = None
    is_active: Optional[bool] = None


class WalletConnectionResponse(WalletConnectionBase):
    """Schema for wallet connection response."""
    id: str
    company_id: str
    is_active: bool
    is_verified: bool
    verification_method: Optional[str] = None
    verification_timestamp: Optional[datetime] = None
    created_at: datetime
    last_activity: Optional[datetime] = None
    
    @classmethod
    def from_orm(cls, obj):
        """Convert ORM object to response schema, handling UUID serialization."""
        data = {
            "id": str(obj.id),
            "company_id": str(obj.company_id),
            "wallet_address": obj.wallet_address,
            "wallet_type": obj.wallet_type,
            "network": obj.network,
            "wallet_name": obj.wallet_name,
            "is_active": obj.is_active,
            "is_verified": obj.is_verified,
            "verification_method": obj.verification_method,
            "verification_timestamp": obj.verification_timestamp,
            "created_at": obj.created_at,
            "last_activity": obj.last_activity
        }
        return cls(**data)
    
    class Config:
        from_attributes = True


class WalletActivityBase(BaseModel):
    """Base wallet activity schema."""
    activity_type: str
    transaction_hash: str
    block_number: Optional[int] = None
    transaction_type: str
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    token_address: Optional[str] = None
    token_symbol: Optional[str] = None
    token_name: Optional[str] = None
    amount: Optional[Decimal] = None
    amount_usd: Optional[Decimal] = None
    inflow_usd: Optional[Decimal] = None
    outflow_usd: Optional[Decimal] = None
    gas_used: Optional[int] = None
    gas_price: Optional[Decimal] = None
    gas_fee_usd: Optional[Decimal] = None
    network: str
    status: str = 'confirmed'
    timestamp: datetime
    transaction_metadata: Optional[Dict[str, Any]] = None


class WalletActivityCreate(WalletActivityBase):
    """Schema for creating wallet activity."""
    wallet_connection_id: uuid.UUID


class WalletActivityResponse(WalletActivityBase):
    """Schema for wallet activity response."""
    id: str
    wallet_connection_id: str
    created_at: datetime
    
    @classmethod
    def from_orm(cls, obj):
        """Convert ORM object to response schema, handling UUID serialization."""
        data = {
            "id": str(obj.id),
            "wallet_connection_id": str(obj.wallet_connection_id),
            "activity_type": obj.activity_type,
            "transaction_hash": obj.transaction_hash,
            "block_number": obj.block_number,
            "transaction_type": obj.transaction_type,
            "from_address": obj.from_address,
            "to_address": obj.to_address,
            "token_address": obj.token_address,
            "token_symbol": obj.token_symbol,
            "amount": float(obj.amount) if obj.amount else 0.0,
            "amount_usd": float(obj.amount_usd) if obj.amount_usd else 0.0,
            "gas_used": obj.gas_used,
            "gas_price": float(obj.gas_price) if obj.gas_price else 0.0,
            "gas_fee_usd": float(obj.gas_fee_usd) if obj.gas_fee_usd else 0.0,
            "network": obj.network,
            "status": obj.status,
            "timestamp": obj.timestamp,
            "transaction_metadata": obj.transaction_metadata,
            "created_at": obj.created_at
        }
        return cls(**data)
    
    class Config:
        from_attributes = True


class WalletVerificationRequest(BaseModel):
    """Schema for wallet verification request."""
    wallet_address: str
    signature: str
    message: str
    timestamp: int


class WalletVerificationResponse(BaseModel):
    """Schema for wallet verification response."""
    verified: bool
    message: str
    wallet_connection_id: Optional[str] = None


class WalletAnalyticsResponse(BaseModel):
    """Schema for wallet analytics response."""
    wallet_address: str
    total_transactions: int
    total_volume_usd: Decimal
    unique_tokens: int
    networks: List[str]
    transaction_types: Dict[str, int]
    daily_activity: List[Dict[str, Any]]
    top_tokens: List[Dict[str, Any]]
    gas_spent_usd: Decimal
    first_transaction: Optional[datetime] = None
    last_transaction: Optional[datetime] = None


# ====================================================================================
# --- User Engagement Tracking Schemas ---
# ====================================================================================

class UserSessionBase(BaseModel):
    """Base user session schema."""
    user_id: str = Field(..., description="User identifier (user_id or anonymous_id)")
    session_id: str = Field(..., description="Session identifier")
    session_start: datetime = Field(..., description="Session start time")
    session_end: Optional[datetime] = Field(None, description="Session end time")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    total_events: int = Field(0, ge=0, description="Total events in session")
    active_time_seconds: int = Field(0, ge=0, description="Total active time in seconds")
    page_views: int = Field(0, ge=0, description="Total page views")
    unique_pages: int = Field(0, ge=0, description="Unique pages viewed")
    country: Optional[str] = Field(None, max_length=2, description="Country code")
    region: Optional[str] = Field(None, max_length=100, description="Region name")
    city: Optional[str] = Field(None, max_length=100, description="City name")
    ip_address: Optional[str] = Field(None, max_length=45, description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    device_type: Optional[str] = Field(None, description="Device type")
    browser: Optional[str] = Field(None, description="Browser name")
    os: Optional[str] = Field(None, description="Operating system")


class UserSessionCreate(UserSessionBase):
    """Schema for creating a user session."""
    company_id: uuid.UUID = Field(..., description="Company ID")


class UserSessionUpdate(BaseModel):
    """Schema for updating a user session."""
    session_end: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    total_events: Optional[int] = Field(None, ge=0)
    active_time_seconds: Optional[int] = Field(None, ge=0)
    page_views: Optional[int] = Field(None, ge=0)
    unique_pages: Optional[int] = Field(None, ge=0)


class UserSessionResponse(UserSessionBase):
    """Schema for user session response."""
    id: str
    company_id: str
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_orm(cls, obj):
        """Convert ORM object to response schema."""
        data = {
            "id": str(obj.id),
            "company_id": str(obj.company_id),
            "user_id": obj.user_id,
            "session_id": obj.session_id,
            "session_start": obj.session_start,
            "session_end": obj.session_end,
            "last_activity": obj.last_activity,
            "total_events": obj.total_events,
            "active_time_seconds": obj.active_time_seconds,
            "page_views": obj.page_views,
            "unique_pages": obj.unique_pages,
            "country": obj.country,
            "region": obj.region,
            "city": obj.city,
            "ip_address": obj.ip_address,
            "user_agent": obj.user_agent,
            "referrer": obj.referrer,
            "device_type": obj.device_type,
            "browser": obj.browser,
            "os": obj.os,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at
        }
        return cls(**data)
    
    class Config:
        from_attributes = True


class UserEngagementBase(BaseModel):
    """Base user engagement schema."""
    user_id: str = Field(..., description="User identifier")
    session_id: str = Field(..., description="Session identifier")
    event_name: str = Field(..., description="Event name")
    event_timestamp: datetime = Field(..., description="Event timestamp")
    engagement_duration_seconds: int = Field(0, ge=0, description="Engagement duration in seconds")
    page_url: Optional[str] = Field(None, description="Page URL")
    page_title: Optional[str] = Field(None, description="Page title")
    event_properties: Dict[str, Any] = Field(default_factory=dict, description="Event properties")
    country: Optional[str] = Field(None, max_length=2, description="Country code")
    region: Optional[str] = Field(None, max_length=100, description="Region name")
    city: Optional[str] = Field(None, max_length=100, description="City name")
    ip_address: Optional[str] = Field(None, max_length=45, description="IP address")


class UserEngagementCreate(UserEngagementBase):
    """Schema for creating user engagement."""
    company_id: uuid.UUID = Field(..., description="Company ID")


class UserEngagementResponse(UserEngagementBase):
    """Schema for user engagement response."""
    id: str
    company_id: str
    created_at: datetime
    
    @classmethod
    def from_orm(cls, obj):
        """Convert ORM object to response schema."""
        data = {
            "id": str(obj.id),
            "company_id": str(obj.company_id),
            "user_id": obj.user_id,
            "session_id": obj.session_id,
            "event_name": obj.event_name,
            "event_timestamp": obj.event_timestamp,
            "engagement_duration_seconds": obj.engagement_duration_seconds,
            "page_url": obj.page_url,
            "page_title": obj.page_title,
            "event_properties": obj.event_properties or {},
            "country": obj.country,
            "region": obj.region,
            "city": obj.city,
            "ip_address": obj.ip_address,
            "created_at": obj.created_at
        }
        return cls(**data)
    
    class Config:
        from_attributes = True


class UserActivitySummaryBase(BaseModel):
    """Base user activity summary schema."""
    summary_date: date = Field(..., description="Summary date")
    hour: Optional[int] = Field(None, ge=0, le=23, description="Hour (0-23), null for daily summaries")
    total_active_users: int = Field(0, ge=0, description="Total active users")
    total_new_users: int = Field(0, ge=0, description="Total new users")
    total_returning_users: int = Field(0, ge=0, description="Total returning users")
    total_sessions: int = Field(0, ge=0, description="Total sessions")
    total_engagement_time_seconds: int = Field(0, ge=0, description="Total engagement time in seconds")
    avg_engagement_time_per_user: float = Field(0.0, ge=0.0, description="Average engagement time per user")
    avg_engagement_time_per_session: float = Field(0.0, ge=0.0, description="Average engagement time per session")
    total_events: int = Field(0, ge=0, description="Total events")
    total_page_views: int = Field(0, ge=0, description="Total page views")
    unique_pages_viewed: int = Field(0, ge=0, description="Unique pages viewed")

    # Breakdown fields
    country_breakdown: Dict[str, int] = Field(default_factory=dict, description="Country breakdown")
    region_breakdown: Dict[str, int] = Field(default_factory=dict, description="Region breakdown")
    city_breakdown: Dict[str, int] = Field(default_factory=dict, description="City breakdown")
    device_breakdown: Dict[str, int] = Field(default_factory=dict, description="Device breakdown")
    browser_breakdown: Dict[str, int] = Field(default_factory=dict, description="Browser breakdown")
    operating_system_breakdown: Dict[str, int] = Field(default_factory=dict, description="Operating system breakdown")


class UserActivitySummaryCreate(UserActivitySummaryBase):
    """Schema for creating user activity summary."""
    company_id: uuid.UUID = Field(..., description="Company ID")


class UserActivitySummaryResponse(UserActivitySummaryBase):
    """Schema for user activity summary response."""
    id: str
    company_id: str
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_orm(cls, obj):
        """Convert ORM object to response schema."""
        data = {
            "id": str(obj.id),
            "company_id": str(obj.company_id),
            "summary_date": obj.date,
            "hour": obj.hour,
            "total_active_users": obj.total_active_users,
            "total_new_users": obj.total_new_users,
            "total_returning_users": obj.total_returning_users,
            "total_sessions": obj.total_sessions,
            "total_engagement_time_seconds": obj.total_engagement_time_seconds,
            "avg_engagement_time_per_user": obj.avg_engagement_time_per_user,
            "avg_engagement_time_per_session": obj.avg_engagement_time_per_session,
            "total_events": obj.total_events,
            "total_page_views": obj.total_page_views,
            "unique_pages_viewed": obj.unique_pages_viewed,
            "country_breakdown": obj.country_breakdown or {},
            "region_breakdown": obj.region_breakdown or {},
            "city_breakdown": obj.city_breakdown or {},
            "device_breakdown": obj.device_breakdown or {},
            "browser_breakdown": obj.browser_breakdown or {},
            "operating_system_breakdown": obj.operating_system_breakdown or {},
            "created_at": obj.created_at,
            "updated_at": obj.updated_at
        }
        return cls(**data)
    
    class Config:
        from_attributes = True


# User Analytics Response Schemas
class UserAnalyticsResponse(BaseModel):
    """Schema for user analytics response."""
    total_active_users: int = Field(..., description="Total active users in period")
    total_new_users: int = Field(..., description="Total new users in period")
    total_returning_users: int = Field(..., description="Total returning users in period")
    avg_engagement_time_per_user: float = Field(..., description="Average engagement time per user in seconds")
    avg_engagement_time_per_session: float = Field(..., description="Average engagement time per session in seconds")
    total_sessions: int = Field(..., description="Total sessions in period")
    total_events: int = Field(..., description="Total events in period")
    total_page_views: int = Field(..., description="Total page views in period")
    period_start: datetime = Field(..., description="Period start time")
    period_end: datetime = Field(..., description="Period end time")
    data_source: str = Field(..., description="Data source used for analytics")


class UserEngagementMetrics(BaseModel):
    """Schema for detailed user engagement metrics."""
    user_id: str = Field(..., description="User identifier")
    total_sessions: int = Field(..., description="Total sessions for user")
    total_engagement_time_seconds: int = Field(..., description="Total engagement time in seconds")
    avg_session_duration_seconds: float = Field(..., description="Average session duration in seconds")
    total_events: int = Field(..., description="Total events for user")
    total_page_views: int = Field(..., description="Total page views for user")
    unique_pages_viewed: int = Field(..., description="Unique pages viewed by user")
    first_seen: datetime = Field(..., description="First time user was seen")
    last_seen: datetime = Field(..., description="Last time user was seen")
    is_new_user: bool = Field(..., description="Whether this is a new user in the period")
    country: Optional[str] = Field(None, description="User's country")
    device_type: Optional[str] = Field(None, description="User's primary device type")


class UserEngagementTimeSeries(BaseModel):
    """Schema for user engagement time series data."""
    timestamp: datetime = Field(..., description="Timestamp")
    active_users: int = Field(..., description="Active users at this time")
    new_users: int = Field(..., description="New users at this time")
    avg_engagement_time: float = Field(..., description="Average engagement time at this time")
    total_sessions: int = Field(..., description="Total sessions at this time")


class UserEngagementDashboardResponse(BaseModel):
    """Schema for user engagement dashboard response."""
    summary: UserAnalyticsResponse = Field(..., description="Overall summary metrics")
    time_series: List[UserEngagementTimeSeries] = Field(..., description="Time series data")
    top_users: List[UserEngagementMetrics] = Field(..., description="Top users by engagement")
    device_breakdown: Dict[str, int] = Field(..., description="Device type breakdown")
    country_breakdown: Dict[str, int] = Field(..., description="Country breakdown")
    hourly_breakdown: Dict[str, int] = Field(..., description="Hourly activity breakdown")


# ====================================================================================
# --- Payment Tracking Schemas ---
# ====================================================================================

class PaymentStatus(str, Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentSessionBase(BaseModel):
    """Base payment session schema."""
    user_id: str = Field(..., description="User identifier")
    session_id: str = Field(..., description="Session identifier")
    payment_id: str = Field(..., description="External payment ID")
    payment_status: PaymentStatus = Field(..., description="Payment status")
    payment_amount: Optional[Decimal] = Field(None, description="Payment amount")
    payment_currency: Optional[str] = Field(None, max_length=10, description="Payment currency")
    payment_method: Optional[str] = Field(None, max_length=50, description="Payment method")
    wallet_address: Optional[str] = Field(None, description="Wallet address")
    chain_id: Optional[str] = Field(None, description="Blockchain chain ID")
    transaction_hash: Optional[str] = Field(None, description="Transaction hash")
    contract_address: Optional[str] = Field(None, description="Contract address")
    payment_started_at: datetime = Field(..., description="Payment start time")
    payment_completed_at: Optional[datetime] = Field(None, description="Payment completion time")
    payment_failed_at: Optional[datetime] = Field(None, description="Payment failure time")
    page_url: Optional[str] = Field(None, description="Page URL where payment was initiated")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    user_agent: Optional[str] = Field(None, description="User agent string")
    country: Optional[str] = Field(None, max_length=2, description="Country code")
    region: Optional[str] = Field(None, max_length=100, description="Region name")
    city: Optional[str] = Field(None, max_length=100, description="City name")
    ip_address: Optional[str] = Field(None, max_length=45, description="IP address")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional properties")


class PaymentSessionCreate(PaymentSessionBase):
    """Schema for creating a payment session."""
    company_id: uuid.UUID = Field(..., description="Company ID")


class PaymentSessionUpdate(BaseModel):
    """Schema for updating a payment session."""
    payment_status: Optional[PaymentStatus] = None
    payment_amount: Optional[Decimal] = None
    payment_currency: Optional[str] = Field(None, max_length=10)
    payment_method: Optional[str] = Field(None, max_length=50)
    transaction_hash: Optional[str] = None
    contract_address: Optional[str] = None
    payment_completed_at: Optional[datetime] = None
    payment_failed_at: Optional[datetime] = None
    properties: Optional[Dict[str, Any]] = None


class PaymentSessionResponse(PaymentSessionBase):
    """Schema for payment session response."""
    id: str
    company_id: str
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_orm(cls, obj):
        """Convert ORM object to response schema."""
        data = {
            "id": str(obj.id),
            "company_id": str(obj.company_id),
            "user_id": obj.user_id,
            "session_id": obj.session_id,
            "payment_id": obj.payment_id,
            "payment_status": obj.payment_status,
            "payment_amount": obj.payment_amount,
            "payment_currency": obj.payment_currency,
            "payment_method": obj.payment_method,
            "wallet_address": obj.wallet_address,
            "chain_id": obj.chain_id,
            "transaction_hash": obj.transaction_hash,
            "contract_address": obj.contract_address,
            "payment_started_at": obj.payment_started_at,
            "payment_completed_at": obj.payment_completed_at,
            "payment_failed_at": obj.payment_failed_at,
            "page_url": obj.page_url,
            "referrer": obj.referrer,
            "user_agent": obj.user_agent,
            "country": obj.country,
            "region": obj.region,
            "city": obj.city,
            "ip_address": obj.ip_address,
            "properties": obj.properties or {},
            "created_at": obj.created_at,
            "updated_at": obj.updated_at
        }
        return cls(**data)


class PaymentAnalyticsResponse(BaseModel):
    """Schema for payment analytics response."""
    total_payments: int
    completed_payments: int
    failed_payments: int
    pending_payments: int
    cancelled_payments: int
    completion_rate: float
    total_revenue: Decimal
    average_payment_amount: Decimal
    payment_methods_breakdown: Dict[str, int]
    currency_breakdown: Dict[str, int]
    chain_breakdown: Dict[str, int]
    recent_payments: List[PaymentSessionResponse]
    conversion_funnel: Dict[str, int]  # started -> completed -> failed


# ====================================================================================
# --- Admin Schemas: Models for admin endpoints. ---
# ====================================================================================
class CompanyWithEvents(BaseModel):
    """Schema for company with event count."""
    company_id: uuid.UUID
    company_name: str
    platform_user_id: uuid.UUID
    total_events: int

class UserWithCompanies(BaseModel):
    """Schema for user with their companies."""
    user_id: uuid.UUID
    user_email: str
    user_name: Optional[str] = None
    is_admin: bool
    companies: List[Dict[str, Any]]  # List of {"id": uuid, "name": str}

class AdminOverviewResponse(BaseModel):
    """Schema for admin overview response."""
    total_users: int
    total_companies: int
    users_with_companies: List[UserWithCompanies]
    companies_with_events: List[CompanyWithEvents]

# ====================================================================================
# --- Team Schemas: Models for managing teams and permissions. ---
# ====================================================================================
class TeamRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class MembershipStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"


class TeamMembershipBase(BaseModel):
    email: EmailStr
    role: TeamRole = TeamRole.EDITOR


class TeamMembershipCreate(TeamMembershipBase):
    pass


class TeamMembershipResponse(TeamMembershipBase):
    id: uuid.UUID
    company_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    status: MembershipStatus
    invited_by_user_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TeamInviteCreate(BaseModel):
    email: EmailStr
    role: TeamRole = TeamRole.EDITOR
    message: Optional[str] = None


class TeamInviteResponse(BaseModel):
    membership: TeamMembershipResponse
    invite_token: str


class TeamActivityType(str, Enum):
    INVITE_SENT = "invite_sent"
    INVITE_ACCEPTED = "invite_accepted"
    MEMBERSHIP_ROLE_CHANGED = "membership_role_changed"
    MEMBER_REMOVED = "member_removed"
    COMPANY_CREATED = "company_created"
    CAMPAIGN_CREATED = "campaign_created"
    CAMPAIGN_UPDATED = "campaign_updated"
    CAMPAIGN_DELETED = "campaign_deleted"


class TeamActivityEntry(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    action_type: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PagedEventsResponse(BaseModel):
    """Paginated wrapper for Event list responses."""
    total: int
    limit: int
    offset: int
    items: List[Event]

