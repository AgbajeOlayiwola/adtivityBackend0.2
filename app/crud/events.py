"""Event-related CRUD operations."""

from typing import Optional, List, Tuple
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session

from ..models import Event, Web3Event, ClientCompany
from ..schemas import SDKEventPayload


def create_event(
    db: Session,
    event_name: str,
    event_type: str,
    client_company_id: uuid.UUID,
    user_id: Optional[str] = None,
    anonymous_id: Optional[str] = None,
    session_id: Optional[str] = None,
    properties: Optional[dict] = None,
    timestamp: Optional[datetime] = None,
    country: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Event:
    """Create a new event."""
    db_event = Event(
        event_name=event_name,
        event_type=event_type,
        client_company_id=client_company_id,
        user_id=user_id,
        anonymous_id=anonymous_id,
        session_id=session_id,
        properties=properties or {},
        timestamp=timestamp or datetime.now(timezone.utc),
        country=country,
        region=region,
        city=city,
        ip_address=ip_address,
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


def get_events_for_client_company(
    db: Session,
    client_company_id: uuid.UUID,
    event_type: Optional[str] = None,
) -> List[Event]:
    """Get events for a specific client company."""
    query = db.query(Event).filter(Event.client_company_id == client_company_id)
    
    if event_type:
        query = query.filter(Event.event_type == event_type)
    
    return query.order_by(Event.timestamp.desc()).all()


def create_web3_event(
    db: Session,
    event_name: str,
    client_company_id: uuid.UUID,
    user_id: str,
    wallet_address: str,
    chain_id: str,
    transaction_hash: Optional[str] = None,
    contract_address: Optional[str] = None,
    properties: Optional[dict] = None,
    timestamp: Optional[datetime] = None,
    country: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Web3Event:
    """Create a new Web3 event."""
    db_event = Web3Event(
        event_name=event_name,
        client_company_id=client_company_id,
        user_id=user_id,
        wallet_address=wallet_address,
        chain_id=chain_id,
        transaction_hash=transaction_hash,
        contract_address=contract_address,
        properties=properties or {},
        timestamp=timestamp or datetime.now(timezone.utc),
        country=country,
        region=region,
        city=city,
        ip_address=ip_address,
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


def get_web3_events_for_client_company(
    db: Session, client_company_id: uuid.UUID
) -> List[Web3Event]:
    """Get Web3 events for a specific client company."""
    return db.query(Web3Event).filter(
        Web3Event.client_company_id == client_company_id
    ).order_by(Web3Event.timestamp.desc()).all()


def handle_sdk_event(db: Session, company_id: uuid.UUID, payload: SDKEventPayload) -> Event:
    """Handle a standard SDK event."""
    # Normalize type to uppercase
    event_type = (payload.type or "TRACK").upper()

    # Always require an event name
    event_name = payload.eventName or f"{event_type}_EVENT"

    # Default: try to tie to a user if info exists
    user_id = None
    if payload.user_id or payload.wallet_address:
        from .users import upsert_client_app_user_from_sdk_event
        user = upsert_client_app_user_from_sdk_event(
            db=db,
            email=payload.user_id,
            wallet_address=payload.wallet_address,
            name=None,
            country=payload.country
        )
        if user:
            user_id = str(user.id)

    # Create the event
    return create_event(
        db=db,
        event_name=event_name,
        event_type=event_type,
        client_company_id=company_id,
        user_id=user_id,
        anonymous_id=payload.anonymous_id,
        session_id=payload.session_id,
        properties=payload.properties or {},
        timestamp=payload.timestamp or datetime.now(timezone.utc),
        country=payload.country,
        region=payload.region,
        city=payload.city,
        ip_address=payload.ip_address,
    )


def handle_web3_sdk_event(db: Session, company_id: uuid.UUID, payload: SDKEventPayload) -> Web3Event:
    """Handle a Web3 SDK event."""
    # Extract Web3-specific data
    event_name = payload.eventName or payload.type or "web3_event"
    user_id = payload.user_id or payload.wallet_address or "unknown"
    wallet_address = payload.wallet_address or "unknown"
    chain_id = payload.chain_id or "unknown"
    
    # Create or update user
    if payload.user_id or payload.wallet_address:
        from .users import upsert_client_app_user_from_sdk_event
        upsert_client_app_user_from_sdk_event(
            db=db,
            email=payload.user_id,
            wallet_address=payload.wallet_address,
            name=None,
            country=payload.country
        )
    
    # Create the Web3 event
    return create_web3_event(
        db=db,
        event_name=event_name,
        client_company_id=company_id,
        user_id=user_id,
        wallet_address=wallet_address,
        chain_id=chain_id,
        transaction_hash=payload.transaction_hash,
        contract_address=payload.contract_address,
        properties=payload.properties or {},
        timestamp=payload.timestamp or datetime.now(timezone.utc),
        country=payload.country,
        region=payload.region,
        city=payload.city,
        ip_address=payload.ip_address,
    )


def get_all_events_for_user(
    db: Session,
    platform_user_id: uuid.UUID,
    company_id: Optional[uuid.UUID] = None,
    limit: int = 100,
    offset: int = 0,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> Tuple[List[Event], int]:
    """Return a paginated list of standard events for a platform user.

    If company_id is provided, only events for that company are returned.
    Otherwise, all events for all companies owned by the user are included.

    Returns a tuple of (events, total_count) where total_count is the number
    of events that match the filters *before* limit/offset are applied.
    """
    import logging
    from sqlalchemy import and_

    logger = logging.getLogger(__name__)
    logger.info(f"🔍 get_all_events_for_user called for platform_user_id={platform_user_id}, company_id={company_id}, limit={limit}, offset={offset}")

    # Build base query of company IDs owned by this user
    company_query = db.query(ClientCompany.id).filter(
        ClientCompany.platform_user_id == platform_user_id
    )

    if company_id:
        # Restrict to the specific company and ensure ownership
        company_query = company_query.filter(ClientCompany.id == company_id)

    company_ids = [row[0] for row in company_query.all()]
    if not company_ids:
        logger.warning(f"⚠️ No companies found for user {platform_user_id} (company filter={company_id})")
        return [], 0

    # Base events query
    events_query = db.query(Event).filter(Event.client_company_id.in_(company_ids))

    # Optional time range filters
    if start_time is not None:
        events_query = events_query.filter(Event.timestamp >= start_time)
    if end_time is not None:
        events_query = events_query.filter(Event.timestamp <= end_time)

    # Compute total before pagination
    total_count = events_query.count()

    # Apply ordering and pagination
    events = (
        events_query
        .order_by(Event.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    logger.info(f"✅ get_all_events_for_user returning {len(events)} events (total={total_count})")
    return events, total_count
