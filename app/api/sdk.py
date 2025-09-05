"""SDK event endpoints for client applications."""

from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import logging
import hashlib

from ..core.database import get_db
from ..core.security import get_current_client_company
from ..core.geolocation import geolocation_service
from ..core.unified_analytics_service import UnifiedAnalyticsService
from .. import crud, schemas, models

router = APIRouter(prefix="/sdk", tags=["SDK Events"])

logger = logging.getLogger(__name__)


def _generate_session_id(company_id: str, user_id: str, anonymous_id: str, client_ip: str) -> str:
    """Generate a deterministic session id per user identity.
    Priority: user_id > anonymous_id > client_ip. No time bucketing.
    """
    principal = user_id or anonymous_id or client_ip or "unknown"
    base = f"{company_id}:{principal}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]


@router.post("/event", status_code=status.HTTP_202_ACCEPTED)
async def receive_sdk_event(
    payloads: Union[schemas.SDKEventPayload, List[schemas.SDKEventPayload]],
    request: Request,
    company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> dict:
    """
    Receive one or multiple events from the client-side SDK.
    Accepts a single object `{...}` or an array `[{...}]`.
    """
    try:
        # Normalize single object -> list
        if isinstance(payloads, schemas.SDKEventPayload):
            payloads = [payloads]

        client_ip = geolocation_service.get_client_ip(request)
        processed_count = 0

        for payload in payloads:
            # Normalize type to uppercase
            if payload.type:
                payload.type = payload.type.upper()

            # Default timestamp if missing
            if not payload.timestamp:
                payload.timestamp = datetime.now(timezone.utc)
            elif isinstance(payload.timestamp, datetime) and payload.timestamp.tzinfo is None:
                payload.timestamp = payload.timestamp.replace(tzinfo=timezone.utc)

            # Enhance payload with IP if missing
            if not payload.ip_address:
                payload.ip_address = client_ip

            # Get location from IP if region data is missing
            if not all([payload.country, payload.region, payload.city]) and payload.ip_address:
                location_data = geolocation_service.get_location_from_ip(payload.ip_address)
                payload.country = payload.country or location_data.get("country")
                payload.region = payload.region or location_data.get("region")
                payload.city = payload.city or location_data.get("city")

            # Ensure session_id (per-user deterministic)
            if not payload.session_id:
                payload.session_id = _generate_session_id(
                    company_id=str(company.id),
                    user_id=payload.user_id or "",
                    anonymous_id=payload.anonymous_id or "",
                    client_ip=client_ip,
                )

            # Detect Web3 event
            is_web3_event = (
                payload.type == schemas.SDKEventType.TX
                or any([
                    payload.wallet_address,
                    payload.chain_id,
                    payload.properties.get("wallet_address"),
                    payload.properties.get("chain_id")
                ])
            )

            # Process through unified analytics service (aggregation system)
            unified_service = UnifiedAnalyticsService(db)
            
            # Prepare event data for the unified service
            event_data = {
                "event_name": payload.eventName or "unknown",
                "event_type": payload.type,
                "user_id": payload.user_id,
                "anonymous_id": payload.anonymous_id,
                "session_id": payload.session_id,
                "properties": payload.properties or {},
                "country": payload.country,
                "region": payload.region,
                "city": payload.city,
                "ip_address": payload.ip_address,
                "timestamp": payload.timestamp,
                "is_web3_event": is_web3_event
            }
            
            # Add Web3-specific fields if it's a Web3 event
            if is_web3_event:
                event_data.update({
                    "wallet_address": payload.wallet_address,
                    "chain_id": payload.chain_id
                })
            
            # Process through aggregation system
            await unified_service.process_sdk_event(str(company.id), event_data)
            
            # Commit the event to database
            db.commit()

            processed_count += 1

        logger.info(f"Successfully processed {processed_count} events for company {company.id}")
        return {"message": f"{processed_count} events received successfully"}

    except Exception as e:
        logger.error(f"Error processing SDK events: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid event payload in batch"
        )