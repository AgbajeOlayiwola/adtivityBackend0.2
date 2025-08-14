"""SDK event endpoints for client applications."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from ..core.database import get_db
from ..core.security import get_current_client_company
from .. import crud, schemas, models

router = APIRouter(prefix="/sdk", tags=["SDK Events"])

logger = logging.getLogger(__name__)


@router.post("/event", status_code=status.HTTP_202_ACCEPTED)
async def receive_sdk_event(
    payloads: List[schemas.SDKEventPayload],
    company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> dict:
    """Receive a batch of events from the client-side SDK."""
    try:
        processed_count = 0
        for payload in payloads:
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