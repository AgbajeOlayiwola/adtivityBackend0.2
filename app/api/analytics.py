"""Analytics endpoints for platform metrics."""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_platform_user, get_current_client_company
from .. import crud, schemas, models

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.post("/metrics/", response_model=schemas.PlatformMetrics, status_code=status.HTTP_201_CREATED)
async def create_metrics(
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
    
    return crud.get_metrics_by_timeframe_for_companies(
        db=db,
        company_ids=company_ids,
        start=start_date,
        end=end_date,
        platform=platform.value,
        chain_id=chain_id
    )


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
    company = crud.get_client_company(db, company_id)
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