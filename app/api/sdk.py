"""SDK event endpoints for client applications."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import logging

from ..core.database import get_db
from ..core.security import get_current_client_company
from ..core.geolocation import geolocation_service
from .. import crud, schemas, models

router = APIRouter(prefix="/sdk", tags=["SDK Events"])

logger = logging.getLogger(__name__)


@router.post("/event", status_code=status.HTTP_202_ACCEPTED)
async def receive_sdk_event(
    payloads: List[schemas.SDKEventPayload],
    request: Request,
    company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> dict:
    """Receive a batch of events from the client-side SDK."""
    try:
        # Get client IP address for geolocation
        client_ip = geolocation_service.get_client_ip(request)
        
        processed_count = 0
        for payload in payloads:
            # Enhance payload with region information if not provided
            if not payload.ip_address:
                payload.ip_address = client_ip
            
            # Get location from IP if region data is missing
            if not all([payload.country, payload.region, payload.city]) and payload.ip_address:
                location_data = geolocation_service.get_location_from_ip(payload.ip_address)
                if not payload.country:
                    payload.country = location_data["country"]
                if not payload.region:
                    payload.region = location_data["region"]
                if not payload.city:
                    payload.city = location_data["city"]
            
            # Determine if this is a Web3 event
            is_web3_event = (
                payload.type == schemas.SDKEventType.TX or
                any([
                    payload.wallet_address,
                    payload.chain_id,
                    payload.properties.get("wallet_address"),
                    payload.properties.get("chain_id")
                ])
            )
            
            if is_web3_event:
                # Handle as a Web3 event
                crud.handle_web3_sdk_event(db, company.id, payload)
            else:
                # Handle as a standard Web2 event
                crud.handle_sdk_event(db, company.id, payload)
            
            processed_count += 1
        
        logger.info(f"Successfully processed {processed_count} events for company {company.id}")
        return {"message": f"{processed_count} events received successfully"}
        
    except Exception as e:
        logger.error(f"Error processing SDK events: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid event payload in batch"
        ) 