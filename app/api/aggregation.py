"""Data aggregation API endpoints."""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..core.database import get_db
from ..core.security import get_current_platform_user, get_current_client_company
from ..core.aggregation_service import AggregationService
from .. import crud, schemas, models

router = APIRouter(prefix="/aggregation", tags=["Data Aggregation"])


@router.post("/subscriptions/", response_model=schemas.SubscriptionPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription_plan(
    subscription: schemas.SubscriptionPlanCreate,
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> schemas.SubscriptionPlanResponse:
    """Create a subscription plan for a company."""
    # Check if company already has a plan
    existing_plan = db.query(models.SubscriptionPlan).filter(
        models.SubscriptionPlan.company_id == current_company.id
    ).first()
    
    if existing_plan:
        raise HTTPException(
            status_code=400, 
            detail="Company already has a subscription plan. Use PUT to update."
        )
    
    # Create new subscription plan
    db_subscription = models.SubscriptionPlan(
        company_id=current_company.id,
        **subscription.model_dump()
    )
    
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    
    return db_subscription


@router.get("/subscriptions/", response_model=schemas.SubscriptionPlanResponse)
async def get_subscription_plan(
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> schemas.SubscriptionPlanResponse:
    """Get the current subscription plan for a company."""
    subscription = db.query(models.SubscriptionPlan).filter(
        models.SubscriptionPlan.company_id == current_company.id
    ).first()
    
    if not subscription:
        # Return default basic plan
        return schemas.SubscriptionPlanResponse(
            id=None,
            company_id=current_company.id,
            plan_name="basic",
            plan_tier=1,
            raw_data_retention_days=0,
            aggregation_frequency="daily",
            max_raw_events_per_month=0,
            max_aggregated_rows_per_month=100000,
            monthly_price_usd=0.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    return subscription


@router.put("/subscriptions/", response_model=schemas.SubscriptionPlanResponse)
async def update_subscription_plan(
    subscription_update: schemas.SubscriptionPlanUpdate,
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> schemas.SubscriptionPlanResponse:
    """Update the subscription plan for a company."""
    subscription = db.query(models.SubscriptionPlan).filter(
        models.SubscriptionPlan.company_id == current_company.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=404, 
            detail="No subscription plan found for this company"
        )
    
    # Update fields
    update_data = subscription_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(subscription, field, value)
    
    subscription.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(subscription)
    
    return subscription


@router.post("/events/", response_model=Dict[str, Any])
async def process_event(
    event_data: schemas.RawEventCreate,
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Process an incoming event based on subscription plan."""
    service = AggregationService(db)
    
    # Add company_id to event data
    event_dict = event_data.model_dump()
    event_dict["company_id"] = current_company.id
    
    # Process the event
    result = await service.process_event(str(current_company.id), event_dict)
    
    return result


@router.post("/aggregate/", response_model=schemas.AggregationResponse)
async def trigger_aggregation(
    aggregation_request: schemas.AggregationRequest,
    background_tasks: BackgroundTasks,
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> schemas.AggregationResponse:
    """Trigger data aggregation for existing raw events."""
    # Verify user owns this company
    company = db.query(models.ClientCompany).filter(
        models.ClientCompany.id == aggregation_request.company_id
    ).first()
    
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Run aggregation in background
    service = AggregationService(db)
    
    def run_aggregation():
        with db.begin():
            return service.aggregate_existing_data(
                str(aggregation_request.company_id),
                aggregation_request.campaign_id,
                aggregation_request.start_date,
                aggregation_request.end_date
            )
    
    # For now, run synchronously (in production, use Celery or similar)
    result = run_aggregation()
    
    return schemas.AggregationResponse(**result)


@router.get("/analytics/daily/", response_model=List[schemas.CampaignAnalyticsDailyResponse])
async def get_daily_analytics(
    campaign_id: str = Query(..., description="Campaign identifier"),
    start_date: date = Query(..., description="Start date for analytics"),
    end_date: date = Query(..., description="End date for analytics"),
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> List[schemas.CampaignAnalyticsDailyResponse]:
    """Get daily analytics for a campaign."""
    analytics = db.query(models.CampaignAnalyticsDaily).filter(
        and_(
            models.CampaignAnalyticsDaily.company_id == current_company.id,
            models.CampaignAnalyticsDaily.campaign_id == campaign_id,
            models.CampaignAnalyticsDaily.date >= start_date,
            models.CampaignAnalyticsDaily.date <= end_date
        )
    ).order_by(models.CampaignAnalyticsDaily.date).all()
    
    return analytics


@router.get("/analytics/hourly/", response_model=List[schemas.CampaignAnalyticsHourlyResponse])
async def get_hourly_analytics(
    campaign_id: str = Query(..., description="Campaign identifier"),
    start_date: date = Query(..., description="Start date for analytics"),
    end_date: date = Query(..., description="End date for analytics"),
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> List[schemas.CampaignAnalyticsHourlyResponse]:
    """Get hourly analytics for a campaign (Pro plan and above)."""
    # Check subscription plan
    subscription = db.query(models.SubscriptionPlan).filter(
        models.SubscriptionPlan.company_id == current_company.id
    ).first()
    
    if not subscription or subscription.plan_tier < 2:
        raise HTTPException(
            status_code=403, 
            detail="Hourly analytics require Pro plan or higher"
        )
    
    analytics = db.query(models.CampaignAnalyticsHourly).filter(
        and_(
            models.CampaignAnalyticsHourly.company_id == current_company.id,
            models.CampaignAnalyticsHourly.campaign_id == campaign_id,
            models.CampaignAnalyticsHourly.date >= start_date,
            models.CampaignAnalyticsHourly.date <= end_date
        )
    ).order_by(
        models.CampaignAnalyticsHourly.date, 
        models.CampaignAnalyticsHourly.hour
    ).all()
    
    return analytics


@router.get("/analytics/raw/", response_model=List[schemas.RawEventResponse])
async def get_raw_events(
    campaign_id: str = Query(..., description="Campaign identifier"),
    start_date: datetime = Query(..., description="Start date for raw events"),
    end_date: datetime = Query(..., description="End date for raw events"),
    limit: int = Query(1000, le=10000, description="Maximum number of events to return"),
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> List[schemas.RawEventResponse]:
    """Get raw events for a campaign (Enterprise plan only)."""
    # Check subscription plan
    subscription = db.query(models.SubscriptionPlan).filter(
        models.SubscriptionPlan.company_id == current_company.id
    ).first()
    
    if not subscription or subscription.plan_tier < 3:
        raise HTTPException(
            status_code=403, 
            detail="Raw event access requires Enterprise plan"
        )
    
    events = db.query(models.RawEvent).filter(
        and_(
            models.RawEvent.company_id == current_company.id,
            models.RawEvent.campaign_id == campaign_id,
            models.RawEvent.event_timestamp >= start_date,
            models.RawEvent.event_timestamp <= end_date
        )
    ).order_by(models.RawEvent.event_timestamp.desc()).limit(limit).all()
    
    return events


@router.get("/storage/savings/", response_model=Dict[str, Any])
async def get_storage_savings(
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get storage savings from aggregation."""
    # Count raw events
    raw_events_count = db.query(models.RawEvent).filter(
        models.RawEvent.company_id == current_company.id
    ).count()
    
    # Count aggregated records
    daily_count = db.query(models.CampaignAnalyticsDaily).filter(
        models.CampaignAnalyticsDaily.company_id == current_company.id
    ).count()
    
    hourly_count = db.query(models.CampaignAnalyticsHourly).filter(
        models.CampaignAnalyticsHourly.company_id == current_company.id
    ).count()
    
    # Calculate storage savings
    raw_storage_mb = raw_events_count * 0.001  # 1KB per event
    aggregated_storage_mb = (daily_count + hourly_count) * 0.01  # 10KB per aggregation
    storage_saved_mb = raw_storage_mb - aggregated_storage_mb
    savings_percentage = (storage_saved_mb / raw_storage_mb * 100) if raw_storage_mb > 0 else 0
    
    return {
        "company_id": current_company.id,
        "raw_events_count": raw_events_count,
        "daily_aggregations_count": daily_count,
        "hourly_aggregations_count": hourly_count,
        "raw_storage_mb": round(raw_storage_mb, 2),
        "aggregated_storage_mb": round(aggregated_storage_mb, 2),
        "storage_saved_mb": round(storage_saved_mb, 2),
        "savings_percentage": round(savings_percentage, 1)
    }


@router.post("/cleanup/", response_model=Dict[str, Any])
async def cleanup_expired_data(
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Clean up expired raw data based on subscription plan."""
    service = AggregationService(db)
    deleted_count = service.cleanup_expired_raw_data(str(current_company.id))
    
    return {
        "company_id": current_company.id,
        "deleted_events_count": deleted_count,
        "message": f"Cleaned up {deleted_count} expired raw events"
    }
