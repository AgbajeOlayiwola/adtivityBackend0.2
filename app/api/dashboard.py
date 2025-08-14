"""Dashboard management endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_platform_user
from .. import crud, schemas, models

router = APIRouter(prefix="/dashboard", tags=["Dashboard Management"])


@router.get("/me", response_model=schemas.PlatformUser)
async def get_current_user_profile(
    current_user: models.PlatformUser = Depends(get_current_platform_user)
) -> models.PlatformUser:
    """Get the profile of the currently authenticated platform user."""
    return current_user


@router.post("/client-companies/", response_model=schemas.ClientCompanyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_company_for_current_user(
    company_input: schemas.ClientCompanyRegisterInput,
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> schemas.ClientCompanyCreateResponse:
    """Create a new client company for the authenticated platform user."""
    # Check if company name already exists
    existing_company = crud.get_client_company_by_name(db, name=company_input.name)
    if existing_company:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client company with this name already exists"
        )
    
    # Create new company
    new_company, raw_api_key = crud.create_client_company_with_api_key(
        db=db,
        name=company_input.name,
        platform_user_id=current_user.id
    )
    
    return schemas.ClientCompanyCreateResponse(
        id=new_company.id,
        name=new_company.name,
        created_at=new_company.created_at,
        is_active=new_company.is_active,
        platform_user_id=new_company.platform_user_id,
        api_key=raw_api_key
    )


@router.get("/client-companies/", response_model=List[schemas.ClientCompany])
async def get_my_client_companies(
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> List[schemas.ClientCompany]:
    """Get all client companies owned by the authenticated platform user."""
    return crud.get_client_companies_by_platform_user(db, platform_user_id=current_user.id)


@router.delete("/client-companies/{company_id}", status_code=status.HTTP_200_OK)
async def delete_client_company(
    company_id: int,
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> dict:
    """Delete a client company and all its associated data."""
    company = crud.get_client_company_by_id(db, company_id=company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client company not found"
        )
    
    if company.platform_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this company"
        )
    
    # TODO: Implement actual deletion logic in CRUD
    # crud.delete_client_company(db, company_id=company_id)
    
    return {"message": f"Client company with ID {company_id} has been deleted"}


@router.get("/client-companies/{company_id}/events", response_model=List[schemas.Event])
async def get_client_company_events(
    company_id: int,
    event_type: schemas.SDKEventType = Query(None, description="Filter events by type"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> List[schemas.Event]:
    """Get all standard (Web2) events for a specific client company."""
    company = crud.get_client_company_by_id(db, company_id=company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view events for this company"
        )
    
    return crud.get_events_for_client_company(
        db,
        client_company_id=company_id,
        event_type=event_type
    )


@router.get("/client-companies/{company_id}/web3-events", response_model=List[schemas.Web3Event])
async def get_client_company_web3_events(
    company_id: int,
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> List[schemas.Web3Event]:
    """Get all Web3 events for a specific client company."""
    company = crud.get_client_company_by_id(db, company_id=company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view events for this company"
        )
    
    return crud.get_web3_events_for_client_company(db, client_company_id=company_id)


@router.post("/client-companies/{company_id}/regenerate-api-key", response_model=schemas.ClientCompanyRegenerateAPIKeyResponse)
async def regenerate_api_key_for_company(
    company_id: int,
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> schemas.ClientCompanyRegenerateAPIKeyResponse:
    """Regenerate a new API key for a specific client company."""
    company = crud.get_client_company_by_id(db, company_id=company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to regenerate API key for this company"
        )
    
    new_company, raw_api_key = crud.regenerate_client_company_api_key(db, company_id=company_id)
    
    return schemas.ClientCompanyRegenerateAPIKeyResponse(
        id=new_company.id,
        name=new_company.name,
        created_at=new_company.created_at,
        is_active=new_company.is_active,
        platform_user_id=new_company.platform_user_id,
        api_key=raw_api_key
    )


@router.get("/all-events", response_model=List[schemas.Event])
async def get_all_events(
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> List[schemas.Event]:
    """Get all standard (Web2) events for all client companies associated with the authenticated platform user."""
    return crud.get_all_events_for_user(db=db, platform_user_id=current_user.id) 