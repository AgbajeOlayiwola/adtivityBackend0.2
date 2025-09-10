"""Analytics endpoints for platform metrics."""

import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..core.database import get_db
from ..core.security import get_current_platform_user, get_current_client_company
from ..core.unified_analytics_service import UnifiedAnalyticsService
from .. import crud, schemas, models

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.post("/metrics/", response_model=schemas.PlatformMetrics, status_code=status.HTTP_201_CREATED)
async def create_cmetrics(
    metrics: schemas.MetricsCreate,
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> schemas.PlatformMetrics:
    """Record platform metrics for a specific client company."""
    return crud.create_platform_metric(
        db=db,
        client_company_id=current_company.id,
        **metrics.model_dump()
    )


@router.get("/metrics/", response_model=List[schemas.PlatformMetrics])
async def get_analytics(
    start_date: datetime = Query(..., description="Start date for analytics"),
    end_date: datetime = Query(default_factory=lambda: datetime.now(timezone.utc), description="End date for analytics"),
    platform: schemas.PlatformType = Query(default=schemas.PlatformType.BOTH, description="Platform type filter"),
    chain_id: Optional[str] = Query(None, description="Blockchain chain ID filter"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> List[schemas.PlatformMetrics]:
    """Get analytics data for all companies owned by the authenticated platform user."""
    company_ids = [c.id for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
    if not company_ids:
        return []
    
    # First try to get metrics from platform_metrics table
    platform_metrics = crud.get_metrics_by_timeframe_for_companies(
        db=db,
        company_ids=company_ids,
        start=start_date,
        end=end_date,
        platform=platform.value,
        chain_id=chain_id
    )
    
    # Get companies that have platform_metrics
    companies_with_metrics = set()
    if platform_metrics:
        for metric in platform_metrics:
            companies_with_metrics.add(metric.client_company_id)
    
    # If all companies have platform_metrics, return them
    if len(companies_with_metrics) == len(company_ids):
        return platform_metrics
    
    # Handle mixed scenario: some companies with platform_metrics, some without
    metrics = []
    companies = crud.get_client_companies_by_platform_user(db, current_user.id)
    
    # Add existing platform_metrics
    if platform_metrics:
        metrics.extend(platform_metrics)
    
    # Calculate from raw events for companies without platform_metrics
    for company in companies:
        if str(company.id) in companies_with_metrics:
            continue  # Skip companies that already have platform_metrics
        # Get events from original events table
        events_query = db.query(models.Event).filter(
            and_(
                models.Event.client_company_id == company.id,
                models.Event.timestamp >= start_date,
                models.Event.timestamp <= end_date
            )
        )
        
        # Get Web3 events from original web3_events table
        web3_events_query = db.query(models.Web3Event).filter(
            and_(
                models.Web3Event.client_company_id == company.id,
                models.Web3Event.timestamp >= start_date,
                models.Web3Event.timestamp <= end_date
            )
        )
        
        # Apply platform filter
        if platform == schemas.PlatformType.WEB2:
            web3_events_query = web3_events_query.filter(False)  # No Web3 events
        elif platform == schemas.PlatformType.WEB3:
            events_query = events_query.filter(False)  # No Web2 events
        
        # Apply chain_id filter for Web3 events
        if chain_id:
            web3_events_query = web3_events_query.filter(models.Web3Event.chain_id == chain_id)
        
        # Execute queries
        events = events_query.all()
        web3_events = web3_events_query.all()
        
        # Calculate metrics
        total_events = len(events) + len(web3_events)
        
        # Get unique users from events (both user_id and anonymous_id)
        unique_users = set()
        for event in events:
            # Use user_id if available, otherwise use anonymous_id
            user_identifier = event.user_id or event.anonymous_id
            if user_identifier:
                unique_users.add(user_identifier)
        for event in web3_events:
            # Web3 events only have user_id (no anonymous_id column)
            if event.user_id:
                unique_users.add(event.user_id)
        
        # Get unique sessions
        unique_sessions = set()
        for event in events:
            if event.session_id:
                unique_sessions.add(event.session_id)
        for event in web3_events:
            if event.session_id:
                unique_sessions.add(event.session_id)
        
        # Create metrics entry
            metric = schemas.PlatformMetrics(
            id=str(uuid.uuid4()),
            client_company_id=str(company.id),
                platform_type=platform.value,
                chain_id=chain_id,
            total_events=total_events,
            unique_users=len(unique_users),
            total_sessions=len(unique_sessions),
                created_at=datetime.now(timezone.utc),
            data_source="raw_events"
            )
            metrics.append(metric)
    
    return metrics


@router.get("/regions/", response_model=schemas.RegionAnalyticsResponse)
async def get_region_analytics(
    start_date: datetime = Query(..., description="Start date for analytics"),
    end_date: datetime = Query(default_factory=lambda: datetime.now(timezone.utc), description="End date for analytics"),
    platform: schemas.PlatformType = Query(default=schemas.PlatformType.BOTH, description="Platform type filter"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> schemas.RegionAnalyticsResponse:
    """Get region-based analytics for all companies owned by the authenticated platform user."""
    company_ids = [c.id for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
    if not company_ids:
        return schemas.RegionAnalyticsResponse(
            regions=[],
            total_users=0,
            total_events=0,
            top_countries=[],
            top_cities=[]
        )
    
    return crud.get_region_analytics(
        db=db,
        company_ids=company_ids,
        start=start_date,
        end=end_date,
        platform=platform.value
    )


@router.get("/regions/{company_id}/", response_model=schemas.RegionAnalyticsResponse)
async def get_company_region_analytics(
    company_id: str,
    start_date: datetime = Query(..., description="Start date for analytics"),
    end_date: datetime = Query(default_factory=lambda: datetime.now(timezone.utc), description="End date for analytics"),
    platform: schemas.PlatformType = Query(default=schemas.PlatformType.BOTH, description="Platform type filter"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> schemas.RegionAnalyticsResponse:
    """Get region-based analytics for a specific company."""
    # Verify user owns this company
    company = crud.get_client_company_by_id(db, company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return crud.get_region_analytics(
        db=db,
        company_ids=[company_id],
        start=start_date,
        end=end_date,
        platform=platform.value
    )


@router.get("/users/locations/", response_model=List[schemas.UserLocationData])
async def get_user_locations(
    company_id: Optional[str] = Query(None, description="Filter by specific company ID"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> List[schemas.UserLocationData]:
    """Get location data for users across all companies owned by the authenticated platform user."""
    company_ids = [c.id for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
    if not company_ids:
        return []
    
    if company_id:
        # Verify user owns this company
        if company_id not in [str(c.id) for c in crud.get_client_companies_by_platform_user(db, current_user.id)]:
            raise HTTPException(status_code=404, detail="Company not found")
        company_ids = [company_id]
    
    return crud.get_user_locations(
        db=db,
        company_ids=company_ids,
        country=country
    ) 