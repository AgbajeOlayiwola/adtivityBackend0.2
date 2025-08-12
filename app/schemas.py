from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

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
    id: Optional[int] = None
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

class PlatformUser(PlatformUserBase):
    """
    The complete schema for a PlatformUser, as retrieved from the database.
    It includes database-specific fields like `id` and `created_at`.
    Note the use of `from_attributes = True` for SQLAlchemy compatibility.
    """
    id: int
    created_at: datetime
    last_login: Optional[datetime] = None
    client_companies: List['ClientCompany'] = []

    class Config:
        from_attributes = True
        # The 'ClientCompany' forward reference is resolved with `from __future__ import annotations`.

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
    id: int
    platform_user_id: int
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
    id: int
    platform_user_id: int
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
    id: int
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
    id: int
    client_company_id: int
    timestamp: datetime

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
    id: int
    client_company_id: int
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

    @validator('type', pre=True, always=True)
    def ensure_valid_event_type(cls, v):
        """
        Validates the event type. If it's not a recognized enum value or is missing,
        it defaults to 'track'. This prevents the SDK from failing on a bad event type.
        """
        if v and v.upper() in SDKEventType.__members__:
            return SDKEventType[v.upper()]
        return SDKEventType.TRACK


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

class PlatformMetrics(MetricsCreate):
    """
    The complete schema for a PlatformMetrics record, as retrieved from the database.
    """
    id: int
    timestamp: datetime
    client_company_id: int

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
