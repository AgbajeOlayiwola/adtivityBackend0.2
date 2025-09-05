import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from passlib.context import CryptContext
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from .models import (ClientAppUser, ClientCompany, Event, PlatformMetrics,
                     PlatformUser, Web3Event)
from .schemas import SDKEventPayload, SDKEventType, ClientCompanyUpdate # Added ClientCompanyUpdate

# Set up logging for better debugging and monitoring
logger = logging.getLogger(__name__)

# --- Password Hashing Setup ---
# This line sets up our password scrambling tool.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Password Hashing/Verification Helpers ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Checks if a plain password (what someone types) matches a hashed password (what's stored).
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Hashes a plain password (turns it into a scrambled, secure version).
    """
    return pwd_context.hash(password)

# --- Type Aliases ---
UserID = uuid.UUID
MetricID = uuid.UUID

# ----------- PlatformUser Operations -----------
def create_platform_user(
    db: Session,
    email: str,
    hashed_password: str,
    name: Optional[str] = None,
    phone_number: Optional[str] = None,
) -> PlatformUser:
    """
    Creates a new platform user in the database.
    """
    db_user = PlatformUser(
        email=email,
        hashed_password=hashed_password,
        name=name,
        phone_number=phone_number,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_platform_user_by_email(db: Session, email: str) -> Optional[PlatformUser]:
    """
    Retrieves a platform user from the database by their email address.
    """
    return db.query(PlatformUser).filter(func.lower(PlatformUser.email) == func.lower(email)).first()

def get_platform_user_by_id(db: Session, user_id: uuid.UUID) -> Optional[PlatformUser]:
    """
    Retrieves a platform user from the database by their unique ID.
    """
    return db.query(PlatformUser).filter(PlatformUser.id == user_id).first()


def authenticate_platform_user(db: Session, email: str, password: str) -> Optional[PlatformUser]:
    """
    Authenticates a platform user by checking their email and password.
    """
    user = get_platform_user_by_email(db, email=email)
    if not user or not verify_password(password, user.hashed_password) or not user.is_active:
        return None
    return user


# ----------- ClientAppUser Operations -----------
def create_client_app_user(
    db: Session,
    email: str,
    hashed_password: str,
    name: Optional[str] = None,
    country: Optional[str] = None,
    subscription_plan: str = "free",
    billing_id: Optional[str] = None,
    wallet_address: Optional[str] = None,
    wallet_type: Optional[str] = None,
) -> ClientAppUser:
    """
    Creates a new client application user record in the database.
    """
    db_user = ClientAppUser(
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

def get_client_app_user_by_email(db: Session, email: str) -> Optional[ClientAppUser]:
    """Retrieves a client application user by their email address (case-sensitive)."""
    return db.query(ClientAppUser).filter(ClientAppUser.email == email).first()

def get_client_app_user_by_wallet(db: Session, wallet_address: str) -> Optional[ClientAppUser]:
    """Retrieves a client application user by their wallet address (case-insensitive)."""
    return db.query(ClientAppUser).filter(func.lower(ClientAppUser.wallet_address) == func.lower(wallet_address)).first()

def get_client_app_user(db: Session, user_id: int) -> Optional[ClientAppUser]:
    """Retrieves a client application user by their unique ID."""
    return db.query(ClientAppUser).filter(ClientAppUser.id == user_id).first()

def update_client_app_user_verification(db: Session, user_id: UserID, is_verified: bool) -> ClientAppUser:
    """Updates the email verification status for a client application user."""
    user = db.query(ClientAppUser).filter(ClientAppUser.id == user_id).first()
    if not user:
        raise ValueError("Client App User not found")
    setattr(user, "is_verified", is_verified)
    db.commit()
    db.refresh(user)
    return user

def upsert_client_app_user_from_sdk_event(
    db: Session,
    sdk_user_id: str,
    properties: Dict[str, Any],
    anonymous_id: Optional[str] = None,
    timestamp: Optional[datetime] = None
) -> ClientAppUser:
    """
    Creates a new client application user or updates an existing one based on an SDK "identify" event.
    """
    existing_user = None
    user_email = properties.get("email")
    user_wallet_address = properties.get("wallet_address")

    if user_email:
        existing_user = get_client_app_user_by_email(db, user_email)
    
    if not existing_user and user_wallet_address:
        existing_user = get_client_app_user_by_wallet(db, user_wallet_address)

    if not existing_user:
        if not user_email and not user_wallet_address:
            raise ValueError("Cannot create client app user without email or wallet_address from identify event.")

        new_user = ClientAppUser(
            email=user_email if user_email else f"anonymous_{sdk_user_id}@example.com",
            hashed_password="sdk_generated_password",
            name=properties.get("name"),
            country=properties.get("country"),
            wallet_address=user_wallet_address,
            wallet_type=properties.get("wallet_type"),
            last_login=timestamp or datetime.now(timezone.utc)
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    else:
        for key, value in properties.items():
            if hasattr(existing_user, key):
                setattr(existing_user, key, value)
        
        existing_user.last_login = timestamp or datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing_user)
        return existing_user

# ----------- ClientCompany Operations -----------
def create_client_company_with_api_key(
    db: Session,
    name: str,
    platform_user_id: int
) -> Tuple[ClientCompany, str]:
    """
    Creates a new client company and associates it with a PlatformUser.
    Returns the new company object and the raw (unhashed) API key.
    """
    raw_api_key = secrets.token_urlsafe(32) # Use a cryptographically secure token
    hashed_key = pwd_context.hash(raw_api_key)

    db_company = ClientCompany(
        name=name,
        api_key_hash=hashed_key,
        platform_user_id=platform_user_id
    )
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    
    return db_company, raw_api_key

def get_client_company_by_api_key(db: Session, api_key: str) -> Optional[ClientCompany]:
    """
    Retrieves a client company by matching the hashed version of their SDK API key.
    """
    companies = db.query(ClientCompany).filter(ClientCompany.api_key_hash is not None).all()
    
    # We must iterate through the companies and verify the hash against the provided key
    # since bcrypt hashes are not directly comparable in a SQL query.
    for c in companies:
        try:
            if pwd_context.verify(api_key, c.api_key_hash):
                return c
        except ValueError:
            # Handle cases where a hash might not be in the correct format for bcrypt.
            continue
    return None

def get_client_company_by_id(db: Session, company_id: uuid.UUID) -> Optional[ClientCompany]:
    """Retrieves a client company by its unique ID."""
    return db.query(ClientCompany).filter(ClientCompany.id == company_id).first()

def get_client_company_by_name(db: Session, name: str) -> Optional[ClientCompany]:
    """
    Retrieves a client company from the database by its name (case-insensitive).
    This function was missing and has been added.
    """
    return db.query(ClientCompany).filter(func.lower(ClientCompany.name) == func.lower(name)).first()

def get_client_companies_by_platform_user(db: Session, platform_user_id: int) -> List[ClientCompany]:
    """
    Retrieves all client companies that are owned by a specific platform user.
    """
    return db.query(ClientCompany).filter(ClientCompany.platform_user_id == platform_user_id).all()

def regenerate_client_company_api_key(db: Session, company: ClientCompany) -> Tuple[ClientCompany, str]:
    """
    Generates a new API key for a company, updates the database with the new hash,
    and returns the new company object along with the raw key.
    """
    # 1. Generate a new, unique API key string using a cryptographically secure method
    raw_api_key = secrets.token_urlsafe(32)

    # 2. Hash the new API key for secure storage using the same context as passwords
    api_key_hash = pwd_context.hash(raw_api_key)

    # 3. Update the company record with the new hash
    company.api_key_hash = api_key_hash
    db.commit()
    db.refresh(company)

    # 4. Return the updated company and the raw key for one-time display
    return company, raw_api_key

def delete_client_company(db: Session, company_id: uuid.UUID):
    """
    Deletes a client company and all associated data, including events and Web3 events.
    This is a permanent and irreversible action.
    """
    # First, get the company to ensure it exists
    company = get_client_company_by_id(db, company_id)
    if not company:
        raise ValueError(f"Client company with ID {company_id} not found.")

    # Delete all associated events for the company
    db.query(Event).filter(Event.client_company_id == company_id).delete(
        synchronize_session=False
    )
    db.query(Web3Event).filter(Web3Event.client_company_id == company_id).delete(
        synchronize_session=False
    )
    db.query(PlatformMetrics).filter(PlatformMetrics.client_company_id == company_id).delete(
        synchronize_session=False
    )

    # Now delete the company itself
    db.delete(company)
    db.commit()

    logger.info(f"Successfully deleted client company with ID {company_id} and all related data.")


def update_client_company(db: Session, company_id: uuid.UUID, company_update: ClientCompanyUpdate) -> Optional[ClientCompany]:
    """
    Updates the details of an existing client company.
    """
    company = get_client_company_by_id(db, company_id)
    if not company:
        return None
    
    # Iterate over the provided update data and apply changes
    update_data = company_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(company, key, value)
    
    db.commit()
    db.refresh(company)
    
    return company


# ----------- Event Operations (Web2 and Web3) -----------
def create_event(
    db: Session,
    eventName: str,
    event_type: str,
    client_company_id: uuid.UUID,
    user_id: Optional[str] = None,
    anonymous_id: Optional[str] = None,
    session_id: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
    timestamp: Optional[datetime] = None,
) -> Event:
    """
    Creates a new standard (Web2) event record in the database, linked to a specific client company.
    """
    db_event = Event(
        event_name=eventName,
        event_type=event_type,
        client_company_id=client_company_id,
        user_id=user_id,
        anonymous_id=anonymous_id,
        session_id=session_id,
        properties=properties,
        timestamp=timestamp or datetime.now(timezone.utc),
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

def get_events_for_client_company(
    db: Session,
    client_company_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    event_type: Optional[SDKEventType] = None
) -> List[Event]:
    """
    Retrieves standard (Web2) events for a given client company, with optional filtering and pagination.
    """
    query = db.query(Event).filter(
        Event.client_company_id == client_company_id
    )
    if event_type:
        query = query.filter(Event.event_type == event_type)
    
    return query.order_by(
        desc(Event.timestamp)
    ).offset(
        skip
    ).limit(
        limit
    ).all()


def create_web3_event(
    db: Session,
    client_company_id: uuid.UUID,
    user_id: str,
    event_name: str,
    wallet_address: str,
    chain_id: str,
    properties: Optional[Dict[str, Any]] = None,
    timestamp: Optional[datetime] = None,
) -> Web3Event:
    """
    Creates a new Web3 event record in the database, linked to a specific client company.
    Note: The transaction_hash and contract_address are now part of the properties dict.
    """
    db_web3_event = Web3Event(
        client_company_id=client_company_id,
        user_id=user_id,
        event_name=event_name,
        wallet_address=wallet_address,
        chain_id=chain_id,
        properties=properties,
        timestamp=timestamp or datetime.now(timezone.utc),
    )
    db.add(db_web3_event)
    db.commit()
    db.refresh(db_web3_event)
    return db_web3_event

def get_web3_events_for_client_company(db: Session, client_company_id: uuid.UUID) -> List[Web3Event]:
    """
    Retrieves all Web3 events associated with a specific client company.
    """
    return db.query(Web3Event).filter(Web3Event.client_company_id == client_company_id).all()

def _parse_timestamp(timestamp_str: Optional[str]) -> datetime:
    """Helper function to safely parse a timestamp string."""
    if not timestamp_str:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except (ValueError, TypeError) as e:
        logger.warning(f"Timestamp parsing error: {e}. Using current UTC time.")
        return datetime.now(timezone.utc)


def handle_sdk_event(
    db: Session,
    client_company_id: uuid.UUID,
    payload: SDKEventPayload,
):
    """
    Processes a single SDK event payload, either creating an event or
    upserting a client app user based on the payload type.
    """
    event_timestamp = _parse_timestamp(payload.timestamp)
    event_type = payload.type
    event_name = payload.eventName

    if event_type == SDKEventType.IDENTIFY:
        if not payload.user_id:
            logger.warning(f"Identify event from company {client_company_id} missing user_id. Skipping.")
            return

        upsert_client_app_user_from_sdk_event(
            db=db,
            sdk_user_id=payload.user_id,
            properties=payload.properties,
            anonymous_id=payload.anonymous_id,
            timestamp=event_timestamp
        )
        logger.info(f"Processed identify event for user {payload.user_id} for company {client_company_id}.")

        # --- NEW LOGIC: ALIASING ANONYMOUS EVENTS ---
        # Find all previous events from this session that were not associated with a user_id
        if payload.anonymous_id:
            anonymous_events = db.query(Event).filter(
                Event.client_company_id == client_company_id,
                Event.anonymous_id == payload.anonymous_id,
                Event.user_id.is_(None)
            ).all()

            # Update their user_id to the newly identified user
            for event in anonymous_events:
                event.user_id = payload.user_id
            
            if anonymous_events:
                db.commit()
                logger.info(f"Aliased {len(anonymous_events)} anonymous events to user {payload.user_id} for company {client_company_id}.")
    
    elif event_type == SDKEventType.TRACK and event_name:
        create_event(
            db=db,
            eventName=event_name,
            event_type=event_type.value,
            client_company_id=client_company_id,
            user_id=payload.user_id,
            anonymous_id=payload.anonymous_id,
            session_id=payload.session_id,
            properties=payload.properties,
            timestamp=event_timestamp,
        )
        logger.info(f"Processed track event '{event_name}' for company {client_company_id}.")

    # --- ADDED LOGIC FOR PAGE_VISIT EVENTS ---
    elif event_type == SDKEventType.PAGE_VISIT:
        create_event(
            db=db,
            eventName="Page Visited",
            event_type=event_type.value,
            client_company_id=client_company_id,
            user_id=payload.user_id,
            anonymous_id=payload.anonymous_id,
            session_id=payload.session_id,
            properties=payload.properties,
            timestamp=event_timestamp,
        )
        logger.info(f"Processed page visit event for company {client_company_id}.")

    else:
        logger.warning(f"Received unhandled event type '{event_type}' for company {client_company_id}: {payload.dict()}. Skipping.")


def handle_web3_sdk_event(
    db: Session,
    client_company_id: uuid.UUID,
    payload: SDKEventPayload,
):
    """
    Processes a Web3 SDK event payload and creates a Web3Event record.
    This function now correctly combines all properties from the payload.
    
    The fix is here:
    1. We first try to get the required fields from the top-level payload.
    2. If a field is missing, we try to find it within the 'properties' dictionary.
    """
    event_timestamp = _parse_timestamp(payload.timestamp)

    # Retrieve wallet_address and chain_id, first from top-level, then from properties.
    wallet_address = payload.wallet_address or payload.properties.get('wallet_address')
    chain_id = payload.chain_id or payload.properties.get('chain_id')
    user_id = payload.user_id or payload.properties.get('user_id')

    # Combine all properties into a single dictionary
    event_properties = payload.properties.copy()
    if payload.transaction_hash:
        event_properties['transaction_hash'] = payload.transaction_hash
    if payload.contract_address:
        event_properties['contract_address'] = payload.contract_address

    # Updated validation check to use the new variables
    if not user_id or not wallet_address or not chain_id:
        logger.warning(f"Web3 event from company {client_company_id} missing required fields (user_id, wallet_address, or chain_id). Skipping.")
        return

    create_web3_event(
        db=db,
        client_company_id=client_company_id,
        user_id=user_id,
        event_name=payload.eventName,
        wallet_address=wallet_address,
        chain_id=chain_id,
        properties=event_properties,
        timestamp=event_timestamp,
    )
    logger.info(f"Processed Web3 event '{payload.eventName}' for company {client_company_id} and wallet {wallet_address}.")


# ----------- Metrics Operations -----------
def create_platform_metric(
    db: Session,
    client_company_id: uuid.UUID,
    total_users: int = 0,
    active_sessions: int = 0,
    conversion_rate: float = 0.0,
    revenue_usd: float = 0.0,
    total_value_locked: float = 0.0,
    active_wallets: int = 0,
    transaction_volume_24h: float = 0.0,
    new_contracts: int = 0,
    daily_page_views: int = 0,
    sales_count: int = 0,
    platform: str = "both",
    source: Optional[str] = None,
    chain_id: Optional[str] = None,
    contract_address: Optional[str] = None,
    # New region tracking fields
    country: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
) -> PlatformMetrics:
    """
    Creates a new platform metrics record in the database, now associated with a client company.
    """
    metric = PlatformMetrics(
        timestamp=datetime.now(timezone.utc),
        client_company_id=client_company_id,
        total_users=total_users,
        active_sessions=active_sessions,
        conversion_rate=conversion_rate,
        revenue_usd=revenue_usd,
        total_value_locked=total_value_locked,
        active_wallets=active_wallets,
        transaction_volume_24h=transaction_volume_24h,
        new_contracts=new_contracts,
        daily_page_views=daily_page_views,
        sales_count=sales_count,
        platform=platform,
        source=source,
        chain_id=chain_id,
        contract_address=contract_address,
        # New region tracking fields
        country=country,
        region=region,
        city=city,
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric

def get_metrics_by_timeframe_for_companies(
    db: Session,
    company_ids: List[uuid.UUID],
    start: datetime,
    end: datetime,
    platform: Optional[str] = None,
    chain_id: Optional[str] = None,
) -> List[PlatformMetrics]:
    """
    Retrieves platform metrics for a list of company IDs, filtered by a time range.
    This is used to show a platform user all metrics for all the companies they own.
    """
    if not company_ids:
        return []

    query = db.query(PlatformMetrics).filter(
        PlatformMetrics.client_company_id.in_(company_ids),
        PlatformMetrics.timestamp >= start,
        PlatformMetrics.timestamp <= end
    )
    
    if platform:
        query = query.filter(PlatformMetrics.platform == platform)
    if chain_id:
        query = query.filter(PlatformMetrics.chain_id == chain_id)
        
    return query.order_by(PlatformMetrics.timestamp.asc()).all()

def calculate_growth_rate(db: Session, days: int = 30) -> float:
    """
    Calculates the percentage growth of total users over a specified number of days.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    
    start_metrics = db.query(func.sum(PlatformMetrics.total_users)).filter(
        PlatformMetrics.timestamp >= start,
        PlatformMetrics.timestamp <= start + timedelta(hours=24)
    ).scalar() or 1
    
    end_metrics = db.query(func.sum(PlatformMetrics.total_users)).filter(
        PlatformMetrics.timestamp >= end - timedelta(hours=24),
        PlatformMetrics.timestamp <= end
    ).scalar() or 0
    
    start_value = float(start_metrics)
    end_value = float(end_metrics)
    
    return ((end_value - start_value) / start_value) * 100

def get_all_events_for_user(db: Session, platform_user_id: uuid.UUID):
    """
    Retrieves all standard events for a given platform user by first
    finding all the companies they own, and then fetching all events
    associated with those companies.
    """
    # 1. Get all company IDs for the authenticated user
    company_ids = db.query(ClientCompany.id).filter(
        ClientCompany.platform_user_id == platform_user_id
    ).all()
    
    # The result is a list of tuples, e.g., [(1,), (2,)].
    # We need to flatten it into a simple list of integers.
    company_ids = [id_tuple[0] for id_tuple in company_ids]
    
    # 2. If the user has no companies, return an empty list immediately
    if not company_ids:
        return []

    # 3. Use the company IDs to query for all events
    return db.query(Event).filter(
        Event.client_company_id.in_(company_ids)
    ).all()

# ----------- Region Analytics Operations -----------
def get_region_analytics(
    db: Session,
    company_ids: List[uuid.UUID],
    start: datetime,
    end: datetime,
    platform: str = "both"
) -> Dict[str, Any]:
    """
    Get region-based analytics for specified companies and time period.
    """
    # Base query for events
    events_query = db.query(
        Event.country,
        Event.region,
        Event.city,
        func.count(Event.id).label('event_count'),
        func.count(func.distinct(func.coalesce(Event.user_id, Event.anonymous_id))).label('unique_users')
    ).filter(
        Event.client_company_id.in_(company_ids),
        Event.timestamp >= start,
        Event.timestamp <= end
    )
    
    # Base query for Web3 events
    web3_query = db.query(
        Web3Event.country,
        Web3Event.region,
        Web3Event.city,
        func.count(Web3Event.id).label('event_count'),
        func.count(func.distinct(Web3Event.user_id)).label('unique_users')
    ).filter(
        Web3Event.client_company_id.in_(company_ids),
        Web3Event.timestamp >= start,
        Web3Event.timestamp <= end
    )
    
    # Apply platform filter
    if platform == "web2":
        web3_query = web3_query.filter(False)  # No Web3 events
    elif platform == "web3":
        events_query = events_query.filter(False)  # No Web2 events
    
    # Combine and aggregate results
    all_regions = []
    
    # Process Web2 events
    for result in events_query.group_by(Event.country, Event.region, Event.city).all():
        if result.country and result.country != "Unknown":
            all_regions.append({
                'country': result.country,
                'region': result.region or "Unknown",
                'city': result.city or "Unknown",
                'event_count': result.event_count,
                'user_count': result.unique_users
            })
    
    # Process Web3 events
    for result in web3_query.group_by(Web3Event.country, Web3Event.region, Web3Event.city).all():
        if result.country and result.country != "Unknown":
            all_regions.append({
                'country': result.country,
                'region': result.region or "Unknown",
                'city': result.city or "Unknown",
                'event_count': result.event_count,
                'user_count': result.unique_users
            })
    
    # Aggregate by region
    region_data = {}
    for region in all_regions:
        key = f"{region['country']}_{region['region']}_{region['city']}"
        if key not in region_data:
            region_data[key] = {
                'country': region['country'],
                'region': region['region'],
                'city': region['city'],
                'event_count': 0,
                'user_count': 0
            }
        region_data[key]['event_count'] += region['event_count']
        region_data[key]['user_count'] += region['user_count']
    
    # Convert to list and sort by user count
    regions = list(region_data.values())
    regions.sort(key=lambda x: x['user_count'], reverse=True)
    
    # Calculate totals
    total_users = sum(r['user_count'] for r in regions)
    total_events = sum(r['event_count'] for r in regions)
    
    # Get top countries and cities
    country_counts = {}
    city_counts = {}
    for region in regions:
        country_counts[region['country']] = country_counts.get(region['country'], 0) + region['user_count']
        city_counts[f"{region['city']}, {region['country']}"] = city_counts.get(f"{region['city']}, {region['country']}", 0) + region['user_count']
    
    top_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_cities = sorted(city_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Convert to response format
    region_objects = []
    for region in regions:
        region_objects.append({
            'country': region['country'],
            'region': region['region'],
            'city': region['city'],
            'user_count': region['user_count'],
            'event_count': region['event_count'],
            'conversion_rate': None,  # Could be calculated from other metrics
            'revenue_usd': None       # Could be calculated from other metrics
        })
    
    return {
        'regions': region_objects,
        'total_users': total_users,
        'total_events': total_events,
        'top_countries': [{"country": country[0], "events": country[1]} for country in top_countries],
        'top_cities': [{"city": city[0], "events": city[1]} for city in top_cities]
    }


def get_user_locations(
    db: Session,
    company_ids: List[uuid.UUID],
    country: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get location data for users across specified companies.
    """
    # Query for user locations from events
    events_query = db.query(
        Event.user_id,
        Event.country,
        Event.region,
        Event.city,
        Event.ip_address,
        func.max(Event.timestamp).label('last_seen')
    ).filter(
        Event.client_company_id.in_(company_ids),
        Event.user_id.isnot(None)
    )
    
    # Query for user locations from Web3 events
    web3_query = db.query(
        Web3Event.user_id,
        Web3Event.country,
        Web3Event.region,
        Web3Event.city,
        Web3Event.ip_address,
        func.max(Web3Event.timestamp).label('last_seen')
    ).filter(
        Web3Event.client_company_id.in_(company_ids)
    )
    
    # Apply country filter if specified
    if country:
        events_query = events_query.filter(Event.country == country)
        web3_query = web3_query.filter(Web3Event.country == country)
    
    # Get results
    events_results = events_query.group_by(
        Event.user_id, Event.country, Event.region, Event.city, Event.ip_address
    ).all()
    
    web3_results = web3_query.group_by(
        Web3Event.user_id, Web3Event.country, Web3Event.region, Web3Event.city, Web3Event.ip_address
    ).all()
    
    # Combine and deduplicate results
    user_locations = {}
    
    for result in events_results:
        if result.user_id:
            user_locations[result.user_id] = {
                'user_id': result.user_id,
                'country': result.country,
                'region': result.region,
                'city': result.city,
                'ip_address': result.ip_address,
                'last_seen': result.last_seen
            }
    
    for result in web3_results:
        if result.user_id:
            # Update existing user or add new one
            if result.user_id in user_locations:
                # Keep the most recent location data
                if result.last_seen > user_locations[result.user_id]['last_seen']:
                    user_locations[result.user_id].update({
                        'country': result.country,
                        'region': result.region,
                        'city': result.city,
                        'ip_address': result.ip_address,
                        'last_seen': result.last_seen
                    })
            else:
                user_locations[result.user_id] = {
                    'user_id': result.user_id,
                    'country': result.country,
                    'region': result.region,
                    'city': result.city,
                    'ip_address': result.ip_address,
                    'last_seen': result.last_seen
                }
    
    return list(user_locations.values())
