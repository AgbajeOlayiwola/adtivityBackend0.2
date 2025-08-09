from __future__ import annotations
# This file serves as the "front desk" or "public interface" for your 'app' package.
# It defines what models, schemas (data forms), and CRUD (Create, Read, Update, Delete)
# operations are easily accessible when other parts of your application import from 'app'.
# Think of it as a table of contents for your backend's main components.

# --- 1. Database Core Components ---
# These are the fundamental tools for connecting to and managing your database.
from .database import Base, engine, SessionLocal, get_db
# Base: The foundation for all your database table blueprints.
# engine: The "engine" that drives the connection to your PostgreSQL database.
# SessionLocal: A special "ink and pen" to get a new, clean database notebook (session) for each task.
# get_db: A helper function that provides and manages database sessions for your API endpoints.

# --- 2. Database Model Blueprints (from models.py) ---
# These are the "blueprints" for the different types of data "boxes" (tables) in your database.
# We've updated these to reflect the new "one user can own many companies" structure.
from .models import (
    PlatformUser,      # NEW: Blueprint for users of *your* Adtivity analytics dashboard.
    ClientCompany,     # UPDATED: Blueprint for companies using your SDK, now linked to a PlatformUser.
    ClientAppUser,     # RENAMED: Formerly 'User', now for users of *your clients'* applications.
    PlatformMetrics,   # Blueprint for general analytics data about your platform.
    Event,
    Web3Event # Blueprint for individual events sent by your SDK.
)

# --- 3. Data Forms (Schemas from schemas.py) ---
# These are the "forms" that define the shape and rules for data when it comes into
# or goes out of your API. They ensure data is structured correctly.
from .schemas import (
    # Schemas for PlatformUser (your dashboard users)
    PlatformUserBase,           # Basic form for PlatformUser details.
    PlatformUserCreate,         # Form for creating a new PlatformUser (includes password).
    PlatformUserLogin,          # Form for PlatformUser login (email and password).
    PlatformUser,               # Full form for PlatformUser details (as retrieved from DB).

    # Schemas for ClientCompany (companies using your SDK)
    ClientCompanyBase,              # Basic form for ClientCompany details.
    ClientCompanyRegisterInput,     # Form for a PlatformUser to create a new ClientCompany (just name).
    ClientCompanyCreateResponse,    # Form for the response after creating a ClientCompany (includes raw API key).
    ClientCompanyRegenerateAPIKeyResponse, # Form for returning a newly regenerated API key.
    ClientCompany,                  # Full form for ClientCompany details (as retrieved from DB, no raw key).

    # Schemas for ClientAppUser (users of your clients' applications)
    ClientAppUserBase,          # Basic form for ClientAppUser details.
    ClientAppUserCreate,        # Form for creating a new ClientAppUser (includes password).
    ClientAppUser,              # Full form for ClientAppUser details (as retrieved from DB).

    # Schemas for general platform metrics
    MetricsCreate,              # Form for creating new platform metrics.
    PlatformMetrics,            # Full form for platform metrics (as retrieved from DB).
    PlatformType,               # Enum for platform types (e.g., "web2", "web3").

    # Schemas for authentication tokens and SDK events
    Token,                      # Form for returning JWT access tokens.
    TokenData,                  # Form for decoding JWT access tokens.
    EventBase,                  # Basic form for event details.
    Event,                      # Full form for event details (as retrieved from DB).
    Web3EventBase,              # Basic form for Web3-specific event details.
    Web3Event,                  # Full form for Web3 events (as retrieved from DB).
    SDKEventPayload,            # Form for the data payload received from your SDK.
    SDKEventType,
)

# --- 4. Database Operations (CRUD from crud.py) ---
# These are the "recipes" for performing specific actions (Create, Read, Update, Delete)
# on your database models.
from .crud import (
    # CRUD operations for password hashing
    get_password_hash,
    verify_password,

    # CRUD operations for PlatformUser
    create_platform_user,           # Create a new platform user.
    get_platform_user_by_email,     # Find a platform user by email.
    get_platform_user_by_id,        # Find a platform user by ID.
    authenticate_platform_user,     # Verify platform user login credentials.

    # CRUD operations for ClientAppUser (formerly 'User')
    create_client_app_user,             # Create a new client application user.
    get_client_app_user,                # Find a client application user by ID.
    get_client_app_user_by_email,       # Find a client application user by email.
    get_client_app_user_by_wallet,      # Find a client application user by wallet address.
    update_client_app_user_verification,# Update client app user's verification status.
    upsert_client_app_user_from_sdk_event, # Create or update client app user from SDK event.

    # CRUD operations for ClientCompany
    create_client_company_with_api_key, # CORRECTED: Create a new client company (linked to a PlatformUser).
    get_client_company_by_api_key,      # Find a client company by its SDK API key hash.
    get_client_company_by_id,           # Find a client company by its ID.
    get_client_company_by_name,
    get_client_companies_by_platform_user, # Find all companies owned by a specific PlatformUser.
    regenerate_client_company_api_key,

    # CRUD operations for Events
    create_event,                       # Create a new event record.
    get_events_for_client_company,      # Get all events for a specific client company.
    create_web3_event,
    get_web3_events_for_client_company,
    handle_sdk_event,
    handle_web3_sdk_event,

    # CRUD operations for PlatformMetrics
    create_platform_metric,             # Create a new platform metric record.
    get_metrics_by_timeframe_for_companies, # Get platform metrics for a specific time range for multiple companies.
    calculate_growth_rate               # Calculate growth rate based on metrics.
)

# --- 5. The '__all__' List: What's Publicly Exported ---
# This special Python list defines what names are exposed when someone does
# 'from app import *' (though 'from app import specific_name' is generally preferred).
# It serves as a clear declaration of the public API of your 'app' package.
__all__ = [
    # Database Core
    'Base',
    'engine',
    'SessionLocal',
    'get_db',

    # Models (Blueprints)
    'PlatformUser',
    'ClientCompany',
    'ClientAppUser',
    'PlatformMetrics',
    'Event',
    'Web3Event',

    # Schemas (Data Forms)
    'PlatformUserBase',
    'PlatformUserCreate',
    'PlatformUserLogin',
    'PlatformUser',
    'ClientCompanyBase',
    'ClientCompanyRegisterInput',
    'ClientCompanyCreateResponse',
    'ClientCompanyRegenerateAPIKeyResponse',
    'ClientCompany',
    'ClientAppUserBase',
    'ClientAppUserCreate',
    'ClientAppUser',
    'MetricsCreate',
    'PlatformMetrics',
    'PlatformType',
    'Token',
    'TokenData',
    'EventBase',
    'Event',
    'Web3EventBase',
    'Web3Event',
    'SDKEventPayload',
    'SDKEventType',

    # CRUD Operations (Recipes)
    'get_password_hash',
    'verify_password',
    'create_platform_user',
    'get_platform_user_by_email',
    'get_platform_user_by_id',
    'authenticate_platform_user',
    'create_client_app_user',
    'get_client_app_user',
    'get_client_app_user_by_email',
    'get_client_app_user_by_wallet',
    'update_client_app_user_verification',
    'upsert_client_app_user_from_sdk_event',
    'create_client_company_with_api_key',
    'get_client_company_by_api_key',
    'get_client_company_by_id',
    'get_client_company_by_name',
    'get_client_companies_by_platform_user',
    'regenerate_client_company_api_key',
    'create_event',
    'get_events_for_client_company',
    'create_web3_event',
    'get_web3_events_for_client_company',
    'handle_sdk_event',
    'handle_web3_sdk_event',
    'create_platform_metric',
    'get_metrics_by_timeframe_for_companies',
    'calculate_growth_rate',
]
