"""Event-related CRUD operations."""

from typing import Optional, List
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
    # Extract event data from payload
    event_name = payload.eventName or payload.type or "unknown"
    event_type = payload.type or "track"
    
    # Create or update user if we have identifying information
    user_id = None
    if payload.user_id or payload.wallet_address:
        from .users import upsert_client_app_user_from_sdk_event
        user = upsert_client_app_user_from_sdk_event(
            db=db,
            email=payload.user_id,
            wallet_address=payload.wallet_address,
            name=None,
            country=None
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
        timestamp=payload.timestamp
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
            country=None
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
        timestamp=payload.timestamp
    ) 


def get_all_events_for_user(db: Session, platform_user_id: uuid.UUID):
    """
    Retrieves all standard events for a given platform user by first
    finding all the companies they own, and then fetching all events
    associated with those companies.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔍 get_all_events_for_user called for platform_user_id: {platform_user_id}")
    
    # 1. Get all company IDs for the authenticated user
    company_ids = db.query(ClientCompany.id).filter(
        ClientCompany.platform_user_id == platform_user_id
    ).all()
    
    logger.info(f"📊 Found {len(company_ids)} companies for user {platform_user_id}")
    
    # The result is a list of tuples, e.g., [(uuid1,), (uuid2,)].
    # We need to flatten it into a simple list of UUIDs.
    company_ids = [id_tuple[0] for id_tuple in company_ids]
    
    logger.info(f"🏢 Company IDs: {[str(cid) for cid in company_ids]}")
    
    # 2. If the user has no companies, return an empty list immediately
    if not company_ids:
        logger.warning(f"⚠️ No companies found for user {platform_user_id}, returning empty list")
        return []

    # 3. Use the company IDs to query for all events
    events = db.query(Event).filter(
        Event.client_company_id.in_(company_ids)
    ).all()
    
    logger.info(f"✅ Found {len(events)} events for companies {[str(cid) for cid in company_ids]}")
    
    return events 