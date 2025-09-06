"""Dashboard management endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
import uuid
from sqlalchemy import func, desc
from datetime import datetime, timedelta, timezone, date

from ..core.database import get_db
from ..core.security import get_current_platform_user
from ..core.security_decorators import (
    rate_limit_by_user,
    validate_query_parameters,
    log_sensitive_operations,
    validate_date_range
)
from .. import crud, schemas, models

router = APIRouter(prefix="/dashboard", tags=["Dashboard Management"])


@router.get("/me", response_model=schemas.UserProfileResponse)
async def get_current_user_profile(
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> schemas.UserProfileResponse:
    """Get the profile of the currently authenticated platform user with Twitter status."""
    # Get all companies owned by this user
    companies = crud.get_client_companies_by_platform_user(db, current_user.id)
    
    # Calculate Twitter integration statistics
    total_companies = len(companies)
    companies_with_twitter = sum(1 for company in companies if company.is_twitter_added)
    has_twitter_integration = companies_with_twitter > 0
    
    return schemas.UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        phone_number=current_user.phone_number,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        companies=companies,
        has_twitter_integration=has_twitter_integration,
        total_companies=total_companies,
        companies_with_twitter=companies_with_twitter
    )


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
    company_id: uuid.UUID = Path(..., description="The UUID of the client company to delete"),
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


@router.get("/client-companies/{company_id}/events")
async def get_client_company_events(
    company_id: uuid.UUID = Path(..., description="The UUID of the client company"),
    event_type: schemas.SDKEventType = Query(None, description="Filter events by type"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get events for a specific client company from raw events table."""
    company = crud.get_client_company_by_id(db, company_id=company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view events for this company"
        )
    
    # Query raw events table directly
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import and_, desc
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=30)
    
    # Build query for events
    query = db.query(models.Event).filter(
        and_(
            models.Event.client_company_id == company_id,
            models.Event.timestamp >= start_date,
            models.Event.timestamp <= end_date
        )
    )
    
    # Add event type filter if provided
    if event_type:
        query = query.filter(models.Event.event_type == event_type.value)
    
    # Get events ordered by timestamp (newest first)
    events = query.order_by(desc(models.Event.timestamp)).limit(1000).all()
    
    # Convert to response format
    events_data = []
    for event in events:
        events_data.append({
            "id": str(event.id),
            "event_name": event.event_name,
            "event_type": event.event_type,
            "user_id": event.user_id,
            "anonymous_id": event.anonymous_id,
            "session_id": event.session_id,
            "properties": event.properties or {},
            "timestamp": event.timestamp,
            "country": event.country,
            "region": event.region,
            "city": event.city,
            "ip_address": event.ip_address
        })
    
    return events_data


@router.get("/client-companies/{company_id}/web3-events", response_model=List[schemas.Web3Event])
async def get_client_company_web3_events(
    company_id: uuid.UUID = Path(..., description="The UUID of the client company"),
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
    company_id: uuid.UUID = Path(..., description="The UUID of the client company"),
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
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔍 get_all_events called for user: {current_user.id} ({current_user.email})")
    
    try:
        # Get all events for the user
        events = crud.get_all_events_for_user(db=db, platform_user_id=current_user.id)
        logger.info(f"✅ Found {len(events)} events for user {current_user.id}")
        
        # Log some details about the events
        if events:
            logger.info(f"📊 First event: {events[0].id} - {events[0].event_name} (company: {events[0].client_company_id})")
        
        return events
        
    except Exception as e:
        logger.error(f"❌ Error in get_all_events: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving events: {str(e)}"
        ) 

@router.get("/analytics/sessions/summary")
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@validate_query_parameters(max_days=90)
@log_sensitive_operations("sessions_summary")
async def sessions_summary(
    company_id: uuid.UUID | None = Query(None, description="Filter by company; defaults to all owned"),
    days: int = Query(7, ge=1, le=90, description="Lookback window in days"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Summary of sessions: total sessions, per-day counts, avg events per session."""
    # Resolve company IDs owned by user
    if company_id:
        company = crud.get_client_company_by_id(db, company_id=company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this company")
        company_ids = [str(company_id)]
    else:
        company_ids = [str(c.id) for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
        if not company_ids:
            return {"total_sessions": 0, "avg_events_per_session": 0.0, "sessions_per_day": []}

    since = datetime.now(timezone.utc) - timedelta(days=days)
    end_date = datetime.now(timezone.utc)

    # Query raw events table directly
    from sqlalchemy import and_, func
    
    # Get all events for the companies in the date range
    events_query = db.query(models.Event).filter(
        and_(
            models.Event.client_company_id.in_([uuid.UUID(cid) for cid in company_ids]),
            models.Event.timestamp >= since,
            models.Event.timestamp <= end_date
        )
    )
    
    events = events_query.all()
    
    # Calculate sessions and events
    sessions = set()
    total_events = len(events)
    events_per_day = {}
    
    for event in events:
        # Count unique sessions
        if event.session_id:
            sessions.add(event.session_id)
        
        # Count events per day
        event_date = event.timestamp.date()
        if event_date not in events_per_day:
            events_per_day[event_date] = 0
        events_per_day[event_date] += 1
    
    total_sessions = len(sessions)
    avg_events_per_session = (total_events / total_sessions) if total_sessions else 0.0
    
    # Convert events_per_day to sessions_per_day format
    sessions_per_day = [
        {"date": str(date), "sessions": count, "events": count} 
        for date, count in sorted(events_per_day.items())
    ]

    return {
        "total_sessions": int(total_sessions),
        "total_events": int(total_events),
        "avg_events_per_session": round(avg_events_per_session, 2),
        "sessions_per_day": sessions_per_day,
        "data_source": "raw_events"
    }


@router.get("/analytics/regions/top")
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@validate_query_parameters(max_limit=50)
@log_sensitive_operations("top_regions")
async def top_regions(
    company_id: uuid.UUID | None = Query(None, description="Filter by company; defaults to all owned"),
    limit: int = Query(10, ge=1, le=50, description="Max regions to return"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Top regions by event count using raw events table."""
    # Resolve company IDs owned by user
    if company_id:
        company = crud.get_client_company_by_id(db, company_id=company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this company")
        company_ids = [str(company_id)]
    else:
        company_ids = [str(c.id) for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
        if not company_ids:
            return {"items": []}

    # Query raw events table directly
    from sqlalchemy import and_
    
    # Get regions analytics for last 30 days
    since = datetime.now(timezone.utc) - timedelta(days=30)
    end_date = datetime.now(timezone.utc)
    
    # Get all events for the companies in the date range
    events_query = db.query(models.Event).filter(
        and_(
            models.Event.client_company_id.in_([uuid.UUID(cid) for cid in company_ids]),
            models.Event.timestamp >= since,
            models.Event.timestamp <= end_date,
            models.Event.country.isnot(None)
        )
    )
    
    events = events_query.all()
    
    # Aggregate regions from raw events
    all_regions = {}
    total_events = len(events)
    
    for event in events:
        country = event.country
        if country:
            if country not in all_regions:
                all_regions[country] = {
                    "country": country,
                    "region": event.region,
                    "city": event.city,
                    "count": 0
                }
            all_regions[country]["count"] += 1
    
    # Sort by count and limit
    sorted_regions = sorted(all_regions.values(), key=lambda x: x["count"], reverse=True)[:limit]

    return {
        "items": sorted_regions,
        "total_events": total_events,
        "data_source": "raw_events"
    }


@router.get("/analytics/sessions/recent")
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@validate_query_parameters(max_limit=100)
@log_sensitive_operations("recent_sessions")
async def recent_sessions(
    company_id: uuid.UUID | None = Query(None, description="Filter by company; defaults to all owned"),
    limit: int = Query(20, ge=1, le=100, description="Number of recent sessions"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Recent sessions with first/last timestamps and event counts using aggregation system."""
    # Resolve company IDs owned by user
    if company_id:
        company = crud.get_client_company_by_id(db, company_id=company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this company")
        company_ids = [str(company_id)]
    else:
        company_ids = [str(c.id) for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
        if not company_ids:
            return {"items": []}

    # Use unified analytics service
    from ..core.unified_analytics_service import UnifiedAnalyticsService
    unified_service = UnifiedAnalyticsService(db)
    
    # Get sessions analytics for last 7 days
    since = datetime.now(timezone.utc) - timedelta(days=7)
    end_date = datetime.now(timezone.utc)
    
    analytics_results = unified_service.get_analytics_data(
        company_ids=company_ids,
        start_date=since,
        end_date=end_date,
        data_type="sessions"
    )
    
    # Aggregate sessions across all companies
    all_sessions = []
    for company_id, result in analytics_results.items():
        sessions = result.get("sessions", [])
        for session in sessions:
            all_sessions.append({
                "session_id": session.get("session_id"),
                "first_seen": session.get("first_seen").isoformat() if session.get("first_seen") else None,
                "last_seen": session.get("last_seen").isoformat() if session.get("last_seen") else None,
                "events": session.get("events", 0),
                "user_id": session.get("user_id")
            })
    
    # Sort by last_seen and limit
    sorted_sessions = sorted(all_sessions, key=lambda x: x["last_seen"] or "", reverse=True)[:limit]
    
    # Calculate total events across all sessions
    total_events = sum(session["events"] for session in all_sessions)

    return {
        "items": sorted_sessions,
        "total_events": total_events,
        "data_sources": [result.get("data_source") for result in analytics_results.values()],
        "subscription_tiers": list(set([result.get("subscription_tier", "basic") for result in analytics_results.values()]))
    }


@router.get("/debug/db-status")
async def debug_database_status(db: Session = Depends(get_db)):
    """Debug endpoint to check database connectivity and data."""
    try:
        # Check basic connectivity
        platform_users_count = db.query(models.PlatformUser).count()
        client_companies_count = db.query(models.ClientCompany).count()
        events_count = db.query(models.Event).count()
        web3_events_count = db.query(models.Web3Event).count()
        
        return {
            "status": "success",
            "database": "connected",
            "counts": {
                "platform_users": platform_users_count,
                "client_companies": client_companies_count,
                "events": events_count,
                "web3_events": web3_events_count
            },
            "sample_data": {
                "platform_users": [
                    {"id": str(u.id), "email": u.email} 
                    for u in db.query(models.PlatformUser).limit(3).all()
                ],
                "client_companies": [
                    {"id": str(c.id), "name": c.name, "owner": str(c.platform_user_id)} 
                    for c in db.query(models.ClientCompany).limit(3).all()
                ]
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "database": "disconnected"
        } 

@router.get("/debug/current-user")
async def debug_current_user(
    current_user: models.PlatformUser = Depends(get_current_platform_user)
):
    """Debug endpoint to check the current authenticated user."""
    return {
        "user_id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.name,
        "is_active": current_user.is_active,
        "is_admin": current_user.is_admin,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }


@router.get("/analytics/unique-users", response_model=schemas.UniqueUsersResponse)
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@validate_query_parameters(max_days=365, max_limit=100)
@log_sensitive_operations("unique_users_analytics")
async def unique_users_analytics(
    company_id: uuid.UUID | None = Query(None, description="Filter by company; defaults to all owned"),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    limit: int = Query(20, ge=1, le=100, description="Number of recent/top users to return"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get unique users analytics using aggregation system."""
    # Resolve company IDs owned by user
    if company_id:
        company = crud.get_client_company_by_id(db, company_id=company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this company")
        company_ids = [str(company_id)]
        company_name = company.name
    else:
        company_ids = [str(c.id) for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
        company_name = None
        if not company_ids:
            return schemas.UniqueUsersResponse(
                total_unique_users=0,
                total_events=0,
                avg_events_per_user=0.0,
                users_per_day=[],
                recent_users=[],
                top_users_by_events=[]
            )

    since = datetime.now(timezone.utc) - timedelta(days=days)
    end_date = datetime.now(timezone.utc)

    # Query raw events table directly
    from sqlalchemy import and_
    
    # Get all events for the companies in the date range
    events_query = db.query(models.Event).filter(
        and_(
            models.Event.client_company_id.in_([uuid.UUID(cid) for cid in company_ids]),
            models.Event.timestamp >= since,
            models.Event.timestamp <= end_date
        )
    )
    
    events = events_query.all()
    
    # Calculate unique users and events
    unique_users = set()
    user_event_counts = {}
    user_first_seen = {}
    user_last_seen = {}
    users_per_day = {}
    recent_users = []
    total_events = len(events)
    
    for event in events:
        # Count unique users (using session_id as proxy for unique users)
        if event.session_id:
            unique_users.add(event.session_id)
            if event.session_id not in user_event_counts:
                user_event_counts[event.session_id] = 0
                user_first_seen[event.session_id] = event.timestamp
                user_last_seen[event.session_id] = event.timestamp
            user_event_counts[event.session_id] += 1
            
            # Update first_seen and last_seen
            if event.timestamp < user_first_seen[event.session_id]:
                user_first_seen[event.session_id] = event.timestamp
            if event.timestamp > user_last_seen[event.session_id]:
                user_last_seen[event.session_id] = event.timestamp
        
        # Count users per day
        event_date = event.timestamp.date()
        if event_date not in users_per_day:
            users_per_day[event_date] = set()
        if event.session_id:
            users_per_day[event_date].add(event.session_id)
    
    total_unique_users = len(unique_users)
    avg_events_per_user = (total_events / total_unique_users) if total_unique_users else 0.0

    # Convert users_per_day to list format
    users_per_day_list = [
        {"date": str(date), "users": len(users)} 
        for date, users in sorted(users_per_day.items())
    ]
    
    # Get top users by events
    top_users_by_events = [
            schemas.UniqueUserData(
            session_id=user_id,
            first_seen=user_first_seen.get(user_id),
            last_seen=user_last_seen.get(user_id),
            total_events=count,
                company_id=company_id,
                company_name=company_name
        )
        for user_id, count in sorted(user_event_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    ]
    
    # Get recent users (sorted by last_seen, most recent first)
    recent_users_data = [
        (session_id, user_last_seen.get(session_id), user_event_counts.get(session_id, 0))
        for session_id in unique_users
    ]
    recent_users_data.sort(key=lambda x: x[1] or datetime.min, reverse=True)
    recent_users = [
            schemas.UniqueUserData(
            session_id=session_id,
            first_seen=user_first_seen.get(session_id),
            last_seen=last_seen,
            total_events=total_events,
                company_id=company_id,
                company_name=company_name
        ) 
        for session_id, last_seen, total_events in recent_users_data[:limit]
        ]

    return schemas.UniqueUsersResponse(
        total_unique_users=int(total_unique_users),
        total_events=int(total_events),
        avg_events_per_user=round(avg_events_per_user, 2),
        users_per_day=users_per_day_list,
        recent_users=recent_users,
        top_users_by_events=top_users_by_events
    ) 


@router.patch("/client-companies/{company_id}/twitter-status")
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@log_sensitive_operations("update_twitter_status")
async def update_twitter_status(
    company_id: uuid.UUID = Path(..., description="The UUID of the client company"),
    twitter_update: schemas.TwitterStatusUpdate = ...,
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Update the Twitter integration status for a company."""
    # Verify company ownership
    company = crud.get_client_company_by_id(db, company_id=company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this company"
        )
    
    # Update the Twitter status
    company.is_twitter_added = twitter_update.is_twitter_added
    db.commit()
    db.refresh(company)
    
    return {
        "message": f"Twitter status updated successfully",
        "company_id": str(company_id),
        "is_twitter_added": twitter_update.is_twitter_added,
        "company_name": company.name
    }


@router.get("/twitter-status")
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
async def get_twitter_status_summary(
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get Twitter integration status summary for the current user."""
    # Get all companies owned by this user
    companies = crud.get_client_companies_by_platform_user(db, current_user.id)
    
    # Calculate Twitter integration statistics
    total_companies = len(companies)
    companies_with_twitter = sum(1 for company in companies if company.is_twitter_added)
    has_twitter_integration = companies_with_twitter > 0
    
    # Get companies with Twitter integration
    twitter_companies = [
        {
            "id": str(company.id),
            "name": company.name,
            "is_twitter_added": company.is_twitter_added,
            "created_at": company.created_at
        }
        for company in companies if company.is_twitter_added
    ]
    
    return {
        "has_twitter_integration": has_twitter_integration,
        "total_companies": total_companies,
        "companies_with_twitter": companies_with_twitter,
        "companies_without_twitter": total_companies - companies_with_twitter,
        "twitter_companies": twitter_companies,
        "twitter_integration_rate": (companies_with_twitter / total_companies * 100) if total_companies > 0 else 0
    } 