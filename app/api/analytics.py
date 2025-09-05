"""Analytics endpoints for platform metrics."""

import uuid
from datetime import datetime, timezone, timedelta
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
    """Get analytics data using aggregation system for all companies owned by the authenticated platform user."""
    company_ids = [str(c.id) for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
    if not company_ids:
        return []
    
    # Use unified analytics service for events analytics
    from ..core.unified_analytics_service import UnifiedAnalyticsService
    unified_service = UnifiedAnalyticsService(db)
    
    # Get events analytics from aggregation system
    analytics_results = unified_service.get_analytics_data(
        company_ids=company_ids,
        start_date=start_date,
        end_date=end_date,
        data_type="events"
    )
    
    # Convert to PlatformMetrics format
    metrics = []
    for company_id, result in analytics_results.items():
        # Get company info
        company = crud.get_client_company_by_id(db, company_id)
        if company:
            metric = schemas.PlatformMetrics(
                id=str(uuid.uuid4()),  # Generate new ID for aggregated data
                client_company_id=company_id,
                platform_type=platform.value,
                chain_id=chain_id,
                total_events=result.get("total_events", 0),
                unique_users=result.get("total_unique_users", 0),
                total_sessions=result.get("total_sessions", 0),
                created_at=datetime.now(timezone.utc),
                data_source=result.get("data_source", "aggregation")
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
    """Get region-based analytics using aggregation system for all companies owned by the authenticated platform user."""
    company_ids = [str(c.id) for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
    if not company_ids:
        return schemas.RegionAnalyticsResponse(
            regions=[],
            total_users=0,
            total_events=0,
            top_countries=[],
            top_cities=[]
        )
    
    # Use unified analytics service
    from ..core.unified_analytics_service import UnifiedAnalyticsService
    unified_service = UnifiedAnalyticsService(db)
    
    # Get regions analytics from aggregation system
    analytics_results = unified_service.get_analytics_data(
        company_ids=company_ids,
        start_date=start_date,
        end_date=end_date,
        data_type="regions"
    )
    
    # Aggregate regions across all companies
    all_regions = []
    total_users = 0
    total_events = 0
    countries = {}
    cities = {}
    
    for company_id, result in analytics_results.items():
        regions_data = result.get("regions", [])
        for region in regions_data:
            # Keep the original format that frontend expects
            transformed_region = {
                "country": region.get("country", ""),
                "events": region.get("events", 0)  # Frontend expects 'events' field
            }
            all_regions.append(transformed_region)
            total_events += region.get("events", 0)
            total_users += region.get("users", 0)
            
            # Aggregate countries and cities
            country = region.get("country")
            city = region.get("city")
            if country:
                countries[country] = countries.get(country, 0) + region.get("events", 0)
            if city:
                cities[city] = cities.get(city, 0) + region.get("events", 0)
    
    # Return in format frontend expects (List[Dict] not List[str])
    top_countries = [{"country": k, "events": v} for k, v in sorted(countries.items(), key=lambda x: x[1], reverse=True)[:10]]
    top_cities = [{"city": k, "events": v} for k, v in sorted(cities.items(), key=lambda x: x[1], reverse=True)[:10]]
    
    return schemas.RegionAnalyticsResponse(
        regions=all_regions,
        total_users=total_users,
        total_events=total_events,
        top_countries=top_countries,
        top_cities=top_cities
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
    """Get region-based analytics using aggregation system for a specific company."""
    # Verify user owns this company
    company = crud.get_client_company_by_id(db, company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Use unified analytics service
    from ..core.unified_analytics_service import UnifiedAnalyticsService
    unified_service = UnifiedAnalyticsService(db)
    
    # Get regions analytics from aggregation system
    analytics_results = unified_service.get_analytics_data(
        company_ids=[company_id],
        start_date=start_date,
        end_date=end_date,
        data_type="regions"
    )
    
    # Get result for this specific company
    result = analytics_results.get(company_id, {})
    regions_data = result.get("regions", [])
    
    # Keep the original format that frontend expects
    regions = []
    for region in regions_data:
        regions.append({
            "country": region.get("country"),
            "region": region.get("region"),
            "city": region.get("city"),
            "events": region.get("events", 0)        # Frontend expects 'events' field
        })
    
    # Calculate totals
    total_users = sum(region.get("users", 0) for region in regions_data)
    total_events = sum(region.get("events", 0) for region in regions_data)
    
    # Aggregate countries and cities
    countries = {}
    cities = {}
    for region in regions_data:
        country = region.get("country")
        city = region.get("city")
        if country:
            countries[country] = countries.get(country, 0) + region.get("events", 0)
        if city:
            cities[city] = cities.get(city, 0) + region.get("events", 0)
    
    # Return in format frontend expects (List[Dict] not List[str])
    top_countries = [{"country": k, "events": v} for k, v in sorted(countries.items(), key=lambda x: x[1], reverse=True)[:10]]
    top_cities = [{"city": k, "events": v} for k, v in sorted(cities.items(), key=lambda x: x[1], reverse=True)[:10]]
    
    return schemas.RegionAnalyticsResponse(
        regions=regions,
        total_users=total_users,
        total_events=total_events,
        top_countries=top_countries,
        top_cities=top_cities
    )


@router.get("/users/locations/", response_model=List[schemas.UserLocationData])
async def get_user_locations(
    company_id: Optional[str] = Query(None, description="Filter by specific company ID"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> List[schemas.UserLocationData]:
    """Get location data for users using aggregation system across all companies owned by the authenticated platform user."""
    company_ids = [str(c.id) for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
    if not company_ids:
        return []
    
    if company_id:
        # Verify user owns this company
        if company_id not in [str(c.id) for c in crud.get_client_companies_by_platform_user(db, current_user.id)]:
            raise HTTPException(status_code=404, detail="Company not found")
        company_ids = [company_id]
    
    # Use unified analytics service
    from ..core.unified_analytics_service import UnifiedAnalyticsService
    unified_service = UnifiedAnalyticsService(db)
    
    # Get regions analytics from aggregation system (last 30 days)
    since = datetime.now(timezone.utc) - timedelta(days=30)
    end_date = datetime.now(timezone.utc)
    
    analytics_results = unified_service.get_analytics_data(
        company_ids=company_ids,
        start_date=since,
        end_date=end_date,
        data_type="regions"
    )
    
    # Convert to UserLocationData format
    user_locations = []
    for company_id, result in analytics_results.items():
        regions = result.get("regions", [])
        for region in regions:
            # Filter by country if specified
            if country and region.get("country") != country:
                continue
                
            location_data = schemas.UserLocationData(
                id=str(uuid.uuid4()),
                company_id=company_id,
                country=region.get("country"),
                region=region.get("region"),
                city=region.get("city"),
                user_count=region.get("users", 0),
                event_count=region.get("events", 0),
                created_at=datetime.now(timezone.utc)
            )
            user_locations.append(location_data)
    
    return user_locations 