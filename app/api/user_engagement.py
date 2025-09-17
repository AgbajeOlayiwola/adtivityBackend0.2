"""User engagement analytics API endpoints."""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_platform_user, get_current_client_company
from .. import models, schemas
from ..crud.user_engagement import user_engagement_crud

router = APIRouter(prefix="/user-engagement", tags=["User Engagement"])


@router.post("/sessions/", response_model=schemas.UserSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_user_session(
    session_data: schemas.UserSessionCreate,
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> schemas.UserSessionResponse:
    """Create a new user session."""
    session_data.company_id = current_company.id
    session = user_engagement_crud.create_user_session(db, session_data)
    return schemas.UserSessionResponse.from_orm(session)


@router.get("/sessions/{session_id}/", response_model=schemas.UserSessionResponse)
async def get_user_session(
    session_id: str,
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> schemas.UserSessionResponse:
    """Get a user session by ID."""
    session = user_engagement_crud.get_user_session(db, session_id, str(current_company.id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return schemas.UserSessionResponse.from_orm(session)


@router.put("/sessions/{session_id}/", response_model=schemas.UserSessionResponse)
async def update_user_session(
    session_id: str,
    update_data: schemas.UserSessionUpdate,
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> schemas.UserSessionResponse:
    """Update a user session."""
    session = user_engagement_crud.update_user_session(db, session_id, str(current_company.id), update_data)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return schemas.UserSessionResponse.from_orm(session)


@router.post("/engagement/", response_model=schemas.UserEngagementResponse, status_code=status.HTTP_201_CREATED)
async def create_user_engagement(
    engagement_data: schemas.UserEngagementCreate,
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> schemas.UserEngagementResponse:
    """Create a new user engagement record."""
    engagement_data.company_id = current_company.id
    engagement = user_engagement_crud.create_user_engagement(db, engagement_data)
    return schemas.UserEngagementResponse.from_orm(engagement)


@router.get("/analytics/", response_model=schemas.UserAnalyticsResponse)
async def get_user_analytics(
    start_date: datetime = Query(..., description="Start date for analytics"),
    end_date: datetime = Query(default_factory=lambda: datetime.now(timezone.utc), description="End date for analytics"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> schemas.UserAnalyticsResponse:
    """Get comprehensive user analytics for all companies owned by the authenticated platform user."""
    # Get all companies owned by the user
    companies = db.query(models.ClientCompany).filter(
        models.ClientCompany.platform_user_id == current_user.id
    ).all()
    
    if not companies:
        return schemas.UserAnalyticsResponse(
            total_active_users=0,
            total_new_users=0,
            total_returning_users=0,
            avg_engagement_time_per_user=0.0,
            avg_engagement_time_per_session=0.0,
            total_sessions=0,
            total_events=0,
            total_page_views=0,
            period_start=start_date,
            period_end=end_date,
            data_source="user_engagement"
        )
    
    # Aggregate analytics across all companies
    total_active_users = 0
    total_new_users = 0
    total_returning_users = 0
    total_engagement_time = 0
    total_events = 0
    total_sessions = 0
    total_page_views = 0
    
    for company in companies:
        company_analytics = user_engagement_crud.get_user_analytics(
            db, str(company.id), start_date, end_date
        )
        
        total_active_users += company_analytics.total_active_users
        total_new_users += company_analytics.total_new_users
        total_returning_users += company_analytics.total_returning_users
        total_engagement_time += company_analytics.avg_engagement_time_per_user * company_analytics.total_active_users
        total_events += company_analytics.total_events
        total_sessions += company_analytics.total_sessions
        total_page_views += company_analytics.total_page_views
    
    # Calculate overall averages
    avg_engagement_time_per_user = total_engagement_time / total_active_users if total_active_users > 0 else 0
    avg_engagement_time_per_session = total_engagement_time / total_sessions if total_sessions > 0 else 0
    
    return schemas.UserAnalyticsResponse(
        total_active_users=total_active_users,
        total_new_users=total_new_users,
        total_returning_users=total_returning_users,
        avg_engagement_time_per_user=avg_engagement_time_per_user,
        avg_engagement_time_per_session=avg_engagement_time_per_session,
        total_sessions=total_sessions,
        total_events=total_events,
        total_page_views=total_page_views,
        period_start=start_date,
        period_end=end_date,
        data_source="user_engagement"
    )


@router.get("/analytics/{company_id}/", response_model=schemas.UserAnalyticsResponse)
async def get_company_user_analytics(
    company_id: str,
    start_date: datetime = Query(..., description="Start date for analytics"),
    end_date: datetime = Query(default_factory=lambda: datetime.now(timezone.utc), description="End date for analytics"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> schemas.UserAnalyticsResponse:
    """Get user analytics for a specific company."""
    # Verify user owns this company
    company = db.query(models.ClientCompany).filter(
        models.ClientCompany.id == company_id,
        models.ClientCompany.platform_user_id == current_user.id
    ).first()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return user_engagement_crud.get_user_analytics(db, company_id, start_date, end_date)


@router.get("/analytics/{company_id}/dashboard/", response_model=schemas.UserEngagementDashboardResponse)
async def get_user_engagement_dashboard(
    company_id: str,
    start_date: datetime = Query(..., description="Start date for analytics"),
    end_date: datetime = Query(default_factory=lambda: datetime.now(timezone.utc), description="End date for analytics"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> schemas.UserEngagementDashboardResponse:
    """Get comprehensive user engagement dashboard data for a specific company."""
    # Verify user owns this company
    company = db.query(models.ClientCompany).filter(
        models.ClientCompany.id == company_id,
        models.ClientCompany.platform_user_id == current_user.id
    ).first()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return user_engagement_crud.get_engagement_dashboard_data(db, company_id, start_date, end_date)


@router.get("/analytics/{company_id}/users/", response_model=List[schemas.UserEngagementMetrics])
async def get_user_engagement_metrics(
    company_id: str,
    start_date: datetime = Query(..., description="Start date for analytics"),
    end_date: datetime = Query(default_factory=lambda: datetime.now(timezone.utc), description="End date for analytics"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of users to return"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> List[schemas.UserEngagementMetrics]:
    """Get detailed engagement metrics for top users in a specific company."""
    # Verify user owns this company
    company = db.query(models.ClientCompany).filter(
        models.ClientCompany.id == company_id,
        models.ClientCompany.platform_user_id == current_user.id
    ).first()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return user_engagement_crud.get_user_engagement_metrics(db, company_id, start_date, end_date, limit)


@router.get("/analytics/{company_id}/time-series/", response_model=List[schemas.UserEngagementTimeSeries])
async def get_engagement_time_series(
    company_id: str,
    start_date: datetime = Query(..., description="Start date for analytics"),
    end_date: datetime = Query(default_factory=lambda: datetime.now(timezone.utc), description="End date for analytics"),
    interval_hours: int = Query(1, ge=1, le=24, description="Time interval in hours"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> List[schemas.UserEngagementTimeSeries]:
    """Get time series data for user engagement in a specific company."""
    # Verify user owns this company
    company = db.query(models.ClientCompany).filter(
        models.ClientCompany.id == company_id,
        models.ClientCompany.platform_user_id == current_user.id
    ).first()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return user_engagement_crud.get_engagement_time_series(db, company_id, start_date, end_date, interval_hours)


@router.get("/analytics/{company_id}/active-users/", response_model=List[schemas.UserSessionResponse])
async def get_active_users(
    company_id: str,
    hours_threshold: int = Query(24, ge=1, le=168, description="Hours threshold for active users"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> List[schemas.UserSessionResponse]:
    """Get currently active users for a specific company."""
    # Verify user owns this company
    company = db.query(models.ClientCompany).filter(
        models.ClientCompany.id == company_id,
        models.ClientCompany.platform_user_id == current_user.id
    ).first()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Calculate threshold time
    threshold_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)
    
    # Get active sessions
    active_sessions = user_engagement_crud.get_active_sessions(db, company_id, threshold_time)
    
    return [schemas.UserSessionResponse.from_orm(session) for session in active_sessions]


@router.get("/analytics/{company_id}/new-users/", response_model=List[schemas.UserEngagementMetrics])
async def get_new_users(
    company_id: str,
    start_date: datetime = Query(..., description="Start date for new users"),
    end_date: datetime = Query(default_factory=lambda: datetime.now(timezone.utc), description="End date for new users"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> List[schemas.UserEngagementMetrics]:
    """Get new users for a specific company in a time period."""
    # Verify user owns this company
    company = db.query(models.ClientCompany).filter(
        models.ClientCompany.id == company_id,
        models.ClientCompany.platform_user_id == current_user.id
    ).first()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Get all user metrics and filter for new users
    all_metrics = user_engagement_crud.get_user_engagement_metrics(db, company_id, start_date, end_date, limit=1000)
    new_users = [metric for metric in all_metrics if metric.is_new_user]
    
    return new_users


@router.get("/analytics/{company_id}/engagement-time/", response_model=dict)
async def get_average_engagement_time(
    company_id: str,
    start_date: datetime = Query(..., description="Start date for analytics"),
    end_date: datetime = Query(default_factory=lambda: datetime.now(timezone.utc), description="End date for analytics"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> dict:
    """Get average engagement time metrics for a specific company."""
    # Verify user owns this company
    company = db.query(models.ClientCompany).filter(
        models.ClientCompany.id == company_id,
        models.ClientCompany.platform_user_id == current_user.id
    ).first()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Get analytics data
    analytics = user_engagement_crud.get_user_analytics(db, company_id, start_date, end_date)
    
    return {
        "avg_engagement_time_per_user_seconds": analytics.avg_engagement_time_per_user,
        "avg_engagement_time_per_user_minutes": analytics.avg_engagement_time_per_user / 60,
        "avg_engagement_time_per_session_seconds": analytics.avg_engagement_time_per_session,
        "avg_engagement_time_per_session_minutes": analytics.avg_engagement_time_per_session / 60,
        "total_active_users": analytics.total_active_users,
        "total_sessions": analytics.total_sessions,
        "period_start": analytics.period_start,
        "period_end": analytics.period_end
    }

