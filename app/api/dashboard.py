"""Dashboard management endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
import uuid
from sqlalchemy import func, desc, and_
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
    
    # Get the Twitter profile for user's companies
    twitter_profile = crud.get_twitter_profile_by_platform_user(db, current_user.id)
    
    # Calculate Twitter integration statistics
    total_companies = len(companies)
    companies_with_twitter = sum(1 for company in companies if company.is_twitter_added)
    has_twitter_integration = companies_with_twitter > 0
    
    # Convert Twitter profile to response schema
    twitter_profile_response = None
    if twitter_profile:
        twitter_profile_response = schemas.CompanyTwitterResponse.from_orm(twitter_profile)
    
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
        companies_with_twitter=companies_with_twitter,
        twitter_profile=twitter_profile_response
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


# Web3 Analytics Endpoints
@router.get("/analytics/web3/overview")
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@validate_query_parameters(max_days=365)
@log_sensitive_operations("web3_analytics_overview")
async def web3_analytics_overview(
    company_id: uuid.UUID | None = Query(None, description="Filter by company; defaults to all owned"),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive Web3 analytics overview integrated into main dashboard."""
    # Resolve company IDs owned by user
    if company_id:
        company = crud.get_client_company_by_id(db, company_id=company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized for this company")
        company_ids = [str(company_id)]
    else:
        company_ids = [str(c.id) for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
        if not company_ids:
            return {
                "total_events": 0,
                "total_wallets": 0,
                "total_contracts": 0,
                "total_amount": 0,
                "total_gas_spent": 0,
                "total_inflow": 0,
                "total_outflow": 0,
                "net_balance": 0,
                "active_chains": [],
                "top_wallets": [],
                "top_contracts": [],
                "recent_activity": [],
                "growth_metrics": {},
                "period": {
                    "start_date": None,
                    "end_date": None,
                    "days": days
                }
            }

    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    # Get all Web3 events for the period (SDK events)
    web3_events = db.query(models.Web3Event).filter(
        and_(
            models.Web3Event.client_company_id.in_([uuid.UUID(cid) for cid in company_ids]),
            models.Web3Event.timestamp >= start_date,
            models.Web3Event.timestamp <= end_date
        )
    ).all()
    
    # Get wallet activities for the period (real blockchain data with USD values)
    wallet_activities = db.query(models.WalletActivity).join(models.WalletConnection).filter(
        and_(
            models.WalletConnection.company_id.in_([uuid.UUID(cid) for cid in company_ids]),
            models.WalletActivity.timestamp >= start_date,
            models.WalletActivity.timestamp <= end_date
        )
    ).all()
    
    if not web3_events and not wallet_activities:
        return {
            "total_events": 0,
            "total_wallets": 0,
            "total_contracts": 0,
            "total_amount": 0,
            "total_gas_spent": 0,
            "total_inflow": 0,
            "total_outflow": 0,
            "net_balance": 0,
            "active_chains": [],
            "top_wallets": [],
            "top_contracts": [],
            "recent_activity": [],
            "growth_metrics": {},
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days
            }
        }
    
    # Calculate comprehensive metrics
    unique_wallets = set()
    unique_contracts = set()
    unique_chains = set()
    total_amount = 0
    total_gas_spent = 0
    total_inflow = 0
    total_outflow = 0
    wallet_activity = {}
    contract_activity = {}
    chain_activity = {}
    recent_activity = []
    
    # Process wallet activities first (real blockchain data with USD values)
    for activity in wallet_activities:
        # Only include receive and transfer transactions for volume calculation
        # Exclude token_balance, token_transfer, nft_hold, etc.
        if activity.transaction_type not in ['receive', 'transfer']:
            continue
            
        # Track unique entities from wallet activities
        if activity.from_address:
            unique_wallets.add(activity.from_address)
        if activity.to_address:
            unique_wallets.add(activity.to_address)
        if activity.token_address:
            unique_contracts.add(activity.token_address)
        if activity.network:
            unique_chains.add(activity.network)
        
        # Use real USD values from wallet activities
        event_amount = float(activity.amount_usd or 0)
        event_gas = float(activity.gas_fee_usd or 0)
        
        # Add to totals
        total_amount += event_amount
        total_gas_spent += event_gas
        
        # Add to inflow/outflow totals for balance calculation
        if hasattr(activity, 'inflow_usd') and activity.inflow_usd:
            total_inflow += float(activity.inflow_usd)
        if hasattr(activity, 'outflow_usd') and activity.outflow_usd:
            total_outflow += float(activity.outflow_usd)
        
        # Add to wallet activity tracking
        wallet_addr = activity.from_address or activity.to_address
        if wallet_addr:
            if wallet_addr not in wallet_activity:
                wallet_activity[wallet_addr] = {
                    "wallet_address": wallet_addr,
                    "interaction_count": 0,
                    "total_amount": 0,
                    "total_gas_spent": 0,
                    "contracts_interacted": set(),
                    "chains_used": set()
                }
            
            wallet_activity[wallet_addr]["interaction_count"] += 1
            wallet_activity[wallet_addr]["total_amount"] += event_amount
            wallet_activity[wallet_addr]["total_gas_spent"] += event_gas
            if activity.token_address:
                wallet_activity[wallet_addr]["contracts_interacted"].add(activity.token_address)
            wallet_activity[wallet_addr]["chains_used"].add(activity.network)
        
        # Add to contract activity tracking
        if activity.token_address:
            if activity.token_address not in contract_activity:
                contract_activity[activity.token_address] = {
                    "contract_address": activity.token_address,
                    "interaction_count": 0,
                    "total_amount": 0,
                    "total_gas_spent": 0,
                    "unique_wallets": set(),
                    "chains_used": set()
                }
            
            contract_activity[activity.token_address]["interaction_count"] += 1
            contract_activity[activity.token_address]["total_amount"] += event_amount
            contract_activity[activity.token_address]["total_gas_spent"] += event_gas
            if wallet_addr:
                contract_activity[activity.token_address]["unique_wallets"].add(wallet_addr)
            contract_activity[activity.token_address]["chains_used"].add(activity.network)
        
        # Add to chain activity tracking
        if activity.network:
            if activity.network not in chain_activity:
                chain_activity[activity.network] = {
                    "chain_id": activity.network,
                    "interaction_count": 0,
                    "total_amount": 0,
                    "total_gas_spent": 0,
                    "unique_wallets": set(),
                    "unique_contracts": set()
                }
            
            chain_activity[activity.network]["interaction_count"] += 1
            chain_activity[activity.network]["total_amount"] += event_amount
            chain_activity[activity.network]["total_gas_spent"] += event_gas
            if wallet_addr:
                chain_activity[activity.network]["unique_wallets"].add(wallet_addr)
            if activity.token_address:
                chain_activity[activity.network]["unique_contracts"].add(activity.token_address)
        
        # Add to recent activity
        recent_activity.append({
            "event_name": activity.transaction_type or "transaction",
            "wallet_address": wallet_addr,
            "contract_address": activity.token_address,
            "chain_id": activity.network,
            "amount": event_amount,
            "gas_spent": event_gas,
            "timestamp": activity.timestamp.isoformat()
        })
    
    # Process Web3 events (SDK events) for additional tracking
    for event in web3_events:
        # Track unique entities
        if event.wallet_address:
            unique_wallets.add(event.wallet_address)
        if event.contract_address:
            unique_contracts.add(event.contract_address)
        if event.chain_id:
            unique_chains.add(event.chain_id)
        
        # Track wallet activity
        if event.wallet_address:
            if event.wallet_address not in wallet_activity:
                wallet_activity[event.wallet_address] = {
                    "wallet_address": event.wallet_address,
                    "interaction_count": 0,
                    "total_amount": 0,
                    "total_gas_spent": 0,
                    "contracts_interacted": set(),
                    "chains_used": set()
                }
            
            wallet_activity[event.wallet_address]["interaction_count"] += 1
            wallet_activity[event.wallet_address]["contracts_interacted"].add(event.contract_address)
            wallet_activity[event.wallet_address]["chains_used"].add(event.chain_id)
        
        # Track contract activity
        if event.contract_address:
            if event.contract_address not in contract_activity:
                contract_activity[event.contract_address] = {
                    "contract_address": event.contract_address,
                    "interaction_count": 0,
                    "total_amount": 0,
                    "total_gas_spent": 0,
                    "unique_wallets": set(),
                    "chains_used": set()
                }
            
            contract_activity[event.contract_address]["interaction_count"] += 1
            contract_activity[event.contract_address]["unique_wallets"].add(event.wallet_address)
            contract_activity[event.contract_address]["chains_used"].add(event.chain_id)
        
        # Track chain activity
        if event.chain_id:
            if event.chain_id not in chain_activity:
                chain_activity[event.chain_id] = {
                    "chain_id": event.chain_id,
                    "interaction_count": 0,
                    "total_amount": 0,
                    "total_gas_spent": 0,
                    "unique_wallets": set(),
                    "unique_contracts": set()
                }
            
            chain_activity[event.chain_id]["interaction_count"] += 1
            chain_activity[event.chain_id]["unique_wallets"].add(event.wallet_address)
            if event.contract_address:
                chain_activity[event.chain_id]["unique_contracts"].add(event.contract_address)
        
        # Extract amount and gas from properties
        event_amount = 0
        event_gas = 0
        
        if event.properties:
            # Extract amount from various possible fields
            amount_fields = ['amount', 'value', 'token_amount', 'eth_amount', 'usd_value', 'transaction_value']
            for field in amount_fields:
                if field in event.properties:
                    try:
                        event_amount = float(event.properties[field])
                        break
                    except (ValueError, TypeError):
                        continue
            
            # Extract gas information
            gas_fields = ['gas_fee', 'gas_fee_usd', 'gas_cost', 'gas_cost_usd', 'transaction_fee', 'fee_usd']
            for field in gas_fields:
                if field in event.properties:
                    try:
                        event_gas = float(event.properties[field])
                        break
                    except (ValueError, TypeError):
                        continue
            
            # If no direct gas field, try to calculate from gas_used and gas_price
            if event_gas == 0 and 'gas_used' in event.properties and 'gas_price' in event.properties:
                try:
                    gas_used = float(event.properties['gas_used'])
                    gas_price = float(event.properties['gas_price'])
                    # Convert from wei to ETH (gas_price is typically in wei)
                    event_gas = (gas_used * gas_price) / 1e18
                except (ValueError, TypeError):
                    pass
        
        # Add to totals
        total_amount += event_amount
        total_gas_spent += event_gas
        
        # Add to wallet/contract/chain amounts
        if event.wallet_address and event.wallet_address in wallet_activity:
            wallet_activity[event.wallet_address]["total_amount"] += event_amount
            wallet_activity[event.wallet_address]["total_gas_spent"] += event_gas
        if event.contract_address and event.contract_address in contract_activity:
            contract_activity[event.contract_address]["total_amount"] += event_amount
            contract_activity[event.contract_address]["total_gas_spent"] += event_gas
        if event.chain_id and event.chain_id in chain_activity:
            chain_activity[event.chain_id]["total_amount"] += event_amount
            chain_activity[event.chain_id]["total_gas_spent"] += event_gas
        
        # Collect recent activity (last 20 events)
        if len(recent_activity) < 20:
            recent_activity.append({
                "wallet_address": event.wallet_address,
                "contract_address": event.contract_address,
                "chain_id": event.chain_id,
                "event_name": event.event_name,
                "transaction_hash": event.transaction_hash,
                "timestamp": event.timestamp.isoformat(),
                "amount": event_amount,
                "gas_spent": event_gas
            })
    
    # Format top wallets
    top_wallets = []
    for wallet_addr, data in wallet_activity.items():
        top_wallets.append({
            "wallet_address": wallet_addr,
            "interaction_count": data["interaction_count"],
            "total_amount": data["total_amount"],
            "total_gas_spent": data["total_gas_spent"],
            "contracts_interacted": len(data["contracts_interacted"]),
            "chains_used": len(data["chains_used"])
        })
    top_wallets.sort(key=lambda x: x["interaction_count"], reverse=True)
    
    # Format top contracts
    top_contracts = []
    for contract_addr, data in contract_activity.items():
        top_contracts.append({
            "contract_address": contract_addr,
            "interaction_count": data["interaction_count"],
            "total_amount": data["total_amount"],
            "total_gas_spent": data["total_gas_spent"],
            "unique_wallets": len(data["unique_wallets"]),
            "chains_used": len(data["chains_used"])
        })
    top_contracts.sort(key=lambda x: x["interaction_count"], reverse=True)
    
    # Format active chains
    active_chains = []
    for chain_id, data in chain_activity.items():
        active_chains.append({
            "chain_id": chain_id,
            "interaction_count": data["interaction_count"],
            "total_amount": data["total_amount"],
            "total_gas_spent": data["total_gas_spent"],
            "unique_wallets": len(data["unique_wallets"]),
            "unique_contracts": len(data["unique_contracts"])
        })
    active_chains.sort(key=lambda x: x["interaction_count"], reverse=True)
    
    # Calculate growth metrics (compare with previous period)
    previous_start = start_date - timedelta(days=days)
    previous_events = db.query(models.Web3Event).filter(
        and_(
            models.Web3Event.client_company_id.in_([uuid.UUID(cid) for cid in company_ids]),
            models.Web3Event.timestamp >= previous_start,
            models.Web3Event.timestamp < start_date
        )
    ).count()
    
    current_events = len(web3_events)
    growth_rate = ((current_events - previous_events) / previous_events * 100) if previous_events > 0 else 0
    
    # Calculate net balance from transaction history (for reference)
    net_balance = total_inflow - total_outflow
    
    # Note: For accurate balance, use the real-time balance endpoint:
    # GET /dashboard/analytics/web3/wallet/{wallet_address}/balance
    
    return {
        "total_events": current_events,
        "total_wallets": len(unique_wallets),
        "total_contracts": len(unique_contracts),
        "total_amount": total_amount,
        "total_gas_spent": total_gas_spent,
        "total_inflow": round(total_inflow, 2),
        "total_outflow": round(total_outflow, 2),
        "net_balance": round(net_balance, 2),
        "note": "For accurate real-time balance, use /dashboard/analytics/web3/wallet/{address}/balance",
        "active_chains": active_chains,
        "top_wallets": top_wallets[:10],  # Top 10 wallets
        "top_contracts": top_contracts[:10],  # Top 10 contracts
        "recent_activity": recent_activity,
        "growth_metrics": {
            "events_growth_rate": round(growth_rate, 2),
            "previous_period_events": previous_events,
            "current_period_events": current_events
        },
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days
        }
    }


@router.get("/analytics/web3/wallet/{wallet_address}")
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@validate_query_parameters(max_days=365)
@log_sensitive_operations("web3_wallet_analytics")
async def web3_wallet_analytics(
    wallet_address: str = Path(..., description="Wallet address to analyze"),
    company_id: uuid.UUID | None = Query(None, description="Filter by company; defaults to all owned"),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Monitor a specific wallet address and track all its interactions."""
    # Resolve company IDs owned by user
    if company_id:
        company = crud.get_client_company_by_id(db, company_id=company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized for this company")
        company_ids = [str(company_id)]
    else:
        company_ids = [str(c.id) for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
        if not company_ids:
            raise HTTPException(status_code=404, detail="No companies found for user")

    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    # Get all events for this wallet (Web3Event - SDK events)
    wallet_events = db.query(models.Web3Event).filter(
        and_(
            models.Web3Event.client_company_id.in_([uuid.UUID(cid) for cid in company_ids]),
            models.Web3Event.wallet_address == wallet_address,
            models.Web3Event.timestamp >= start_date,
            models.Web3Event.timestamp <= end_date
        )
    ).order_by(desc(models.Web3Event.timestamp)).all()
    
    # Get wallet activities for this wallet (real blockchain data)
    wallet_activities = db.query(models.WalletActivity).join(models.WalletConnection).filter(
        and_(
            models.WalletConnection.company_id.in_([uuid.UUID(cid) for cid in company_ids]),
            models.WalletActivity.from_address == wallet_address,
            models.WalletActivity.timestamp >= start_date,
            models.WalletActivity.timestamp <= end_date
        )
    ).order_by(desc(models.WalletActivity.timestamp)).all()
    
    if not wallet_events and not wallet_activities:
        return {
            "wallet_address": wallet_address,
            "total_interactions": 0,
            "total_amount": 0,
            "total_gas_spent": 0,
            "total_inflow": 0,
            "total_outflow": 0,
            "net_balance": 0,
            "unique_contracts": [],
            "chains_used": [],
            "interaction_history": [],
            "summary": {
                "first_interaction": None,
                "last_interaction": None,
                "most_active_contract": None,
                "most_active_chain": None
            }
        }
    
    # Analyze wallet interactions
    unique_contracts = set()
    chains_used = set()
    total_amount = 0
    total_gas_spent = 0
    total_inflow = 0
    total_outflow = 0
    contract_interactions = {}
    chain_interactions = {}
    interaction_history = []
    
    # Process wallet activities first (real blockchain data with USD values)
    for activity in wallet_activities:
        # Only include receive and transfer transactions for volume calculation
        if activity.transaction_type not in ['receive', 'transfer']:
            continue
            
        # Track contracts
        if activity.token_address:
            unique_contracts.add(activity.token_address)
            contract_interactions[activity.token_address] = contract_interactions.get(activity.token_address, 0) + 1
        
        # Track chains
        chains_used.add(activity.network)
        chain_interactions[activity.network] = chain_interactions.get(activity.network, 0) + 1
        
        # Use real USD values from wallet activities
        event_amount = float(activity.amount_usd or 0)
        event_gas = float(activity.gas_fee_usd or 0)
        
        # Add to totals
        total_amount += event_amount
        total_gas_spent += event_gas
        
        # Add to inflow/outflow totals for balance calculation
        if hasattr(activity, 'inflow_usd') and activity.inflow_usd:
            total_inflow += float(activity.inflow_usd)
        if hasattr(activity, 'outflow_usd') and activity.outflow_usd:
            total_outflow += float(activity.outflow_usd)
        
        # Add to interaction history
        interaction_history.append({
            "event_name": activity.transaction_type,
            "wallet_address": wallet_address,
            "contract_address": activity.token_address,
            "chain_id": activity.network,
            "amount": event_amount,
            "gas_spent": event_gas,
            "timestamp": activity.timestamp.isoformat()
        })
    
    # Process Web3 events (SDK events) for additional tracking
    for event in wallet_events:
        # Track contracts
        if event.contract_address:
            unique_contracts.add(event.contract_address)
            contract_interactions[event.contract_address] = contract_interactions.get(event.contract_address, 0) + 1
        
        # Track chains
        chains_used.add(event.chain_id)
        chain_interactions[event.chain_id] = chain_interactions.get(event.chain_id, 0) + 1
        
        # Extract amount and gas from properties
        event_amount = 0
        event_gas = 0
        
        if event.properties:
            # Common amount field names in Web3 events
            amount_fields = ['amount', 'value', 'token_amount', 'eth_amount', 'usd_value', 'transaction_value']
            for field in amount_fields:
                if field in event.properties:
                    try:
                        event_amount = float(event.properties[field])
                        break
                    except (ValueError, TypeError):
                        continue
            
            # Extract gas information
            gas_fields = ['gas_fee', 'gas_fee_usd', 'gas_cost', 'gas_cost_usd', 'transaction_fee', 'fee_usd']
            for field in gas_fields:
                if field in event.properties:
                    try:
                        event_gas = float(event.properties[field])
                        break
                    except (ValueError, TypeError):
                        continue
            
            # If no direct gas field, try to calculate from gas_used and gas_price
            if event_gas == 0 and 'gas_used' in event.properties and 'gas_price' in event.properties:
                try:
                    gas_used = float(event.properties['gas_used'])
                    gas_price = float(event.properties['gas_price'])
                    # Convert from wei to ETH (gas_price is typically in wei)
                    event_gas = (gas_used * gas_price) / 1e18
                except (ValueError, TypeError):
                    pass
        
        total_amount += event_amount
        total_gas_spent += event_gas
        
        # Build interaction history
        interaction_history.append({
            "transaction_hash": event.transaction_hash,
            "contract_address": event.contract_address,
            "chain_id": event.chain_id,
            "event_name": event.event_name,
            "amount": event_amount,
            "gas_spent": event_gas,
            "timestamp": event.timestamp.isoformat(),
            "properties": event.properties or {}
        })
    
    # Calculate summary metrics
    most_active_contract = max(contract_interactions.items(), key=lambda x: x[1])[0] if contract_interactions else None
    most_active_chain = max(chain_interactions.items(), key=lambda x: x[1])[0] if chain_interactions else None
    
    # Contract interaction details
    contract_details = []
    for contract_addr, count in contract_interactions.items():
        contract_events = [e for e in wallet_events if e.contract_address == contract_addr]
        contract_amount = sum(
            float(e.properties.get('amount', e.properties.get('value', 0))) 
            for e in contract_events 
            if e.properties and (e.properties.get('amount') or e.properties.get('value'))
        )
        
        contract_details.append({
            "contract_address": contract_addr,
            "interaction_count": count,
            "total_amount": contract_amount,
            "first_interaction": min(e.timestamp for e in contract_events).isoformat(),
            "last_interaction": max(e.timestamp for e in contract_events).isoformat(),
            "chains_used": list(set(e.chain_id for e in contract_events))
        })
    
    # Sort by interaction count
    contract_details.sort(key=lambda x: x["interaction_count"], reverse=True)
    
    # Calculate net balance
    net_balance = total_inflow - total_outflow
    
    return {
        "wallet_address": wallet_address,
        "total_interactions": len(wallet_events),
        "total_amount": total_amount,
        "total_gas_spent": total_gas_spent,
        "total_inflow": round(total_inflow, 2),
        "total_outflow": round(total_outflow, 2),
        "net_balance": round(net_balance, 2),
        "unique_contracts": list(unique_contracts),
        "chains_used": list(chains_used),
        "interaction_history": interaction_history[:100],  # Limit to 100 most recent
        "contract_details": contract_details,
        "summary": {
            "first_interaction": min(e.timestamp for e in wallet_events).isoformat(),
            "last_interaction": max(e.timestamp for e in wallet_events).isoformat(),
            "most_active_contract": most_active_contract,
            "most_active_chain": most_active_chain,
            "avg_amount_per_interaction": round(total_amount / len(wallet_events), 4) if wallet_events else 0,
            "avg_gas_per_interaction": round(total_gas_spent / len(wallet_events), 4) if wallet_events else 0
        }
    }


@router.get("/analytics/web3/wallet/{wallet_address}/balance")
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@log_sensitive_operations("web3_wallet_balance")
async def get_wallet_balance(
    wallet_address: str = Path(..., description="Wallet address to get balance for"),
    network: str = Query("solana", description="Blockchain network"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get real-time wallet balance from blockchain explorer."""
    try:
        from ..core.blockchain_explorer_service import BlockchainExplorerService
        
        explorer_service = BlockchainExplorerService()
        balance_data = await explorer_service.get_wallet_balance(wallet_address, network)
        
        return {
            "wallet_address": wallet_address,
            "network": network,
            "success": balance_data.get("success", False),
            "balance": balance_data.get("balance", 0),
            "balance_usd": balance_data.get("balance_usd", 0),
            "total_value_usd": balance_data.get("total_value_usd", 0),
            "tokens": balance_data.get("tokens", []),
            "error": balance_data.get("error"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching wallet balance: {str(e)}"
        )


@router.get("/analytics/web3/contract/{contract_address}")
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@validate_query_parameters(max_days=365)
@log_sensitive_operations("web3_contract_analytics")
async def web3_contract_analytics(
    contract_address: str = Path(..., description="Contract address to analyze"),
    company_id: uuid.UUID | None = Query(None, description="Filter by company; defaults to all owned"),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Monitor a specific contract address and track all wallet interactions with it."""
    # Resolve company IDs owned by user
    if company_id:
        company = crud.get_client_company_by_id(db, company_id=company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized for this company")
        company_ids = [str(company_id)]
    else:
        company_ids = [str(c.id) for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
        if not company_ids:
            raise HTTPException(status_code=404, detail="No companies found for user")

    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    # Get all events for this contract
    contract_events = db.query(models.Web3Event).filter(
        and_(
            models.Web3Event.client_company_id.in_([uuid.UUID(cid) for cid in company_ids]),
            models.Web3Event.contract_address == contract_address.lower(),
            models.Web3Event.timestamp >= start_date,
            models.Web3Event.timestamp <= end_date
        )
    ).order_by(desc(models.Web3Event.timestamp)).all()
    
    if not contract_events:
        return {
            "contract_address": contract_address,
            "total_interactions": 0,
            "unique_wallets": 0,
            "total_amount": 0,
            "chains_used": [],
            "wallet_interactions": [],
            "summary": {
                "first_interaction": None,
                "last_interaction": None,
                "most_active_wallet": None,
                "most_active_chain": None
            }
        }
    
    # Analyze contract interactions
    unique_wallets = set()
    chains_used = set()
    total_amount = 0
    wallet_interactions = {}
    chain_interactions = {}
    
    for event in contract_events:
        # Track wallets
        unique_wallets.add(event.wallet_address)
        wallet_interactions[event.wallet_address] = wallet_interactions.get(event.wallet_address, 0) + 1
        
        # Track chains
        chains_used.add(event.chain_id)
        chain_interactions[event.chain_id] = chain_interactions.get(event.chain_id, 0) + 1
        
        # Extract amount from properties
        if event.properties:
            amount_fields = ['amount', 'value', 'token_amount', 'eth_amount', 'usd_value']
            for field in amount_fields:
                if field in event.properties:
                    try:
                        total_amount += float(event.properties[field])
                        break
                    except (ValueError, TypeError):
                        continue
    
    # Calculate wallet interaction details
    wallet_details = []
    for wallet_addr, count in wallet_interactions.items():
        wallet_events = [e for e in contract_events if e.wallet_address == wallet_addr]
        wallet_amount = sum(
            float(e.properties.get('amount', e.properties.get('value', 0))) 
            for e in wallet_events 
            if e.properties and (e.properties.get('amount') or e.properties.get('value'))
        )
        
        wallet_details.append({
            "wallet_address": wallet_addr,
            "interaction_count": count,
            "total_amount": wallet_amount,
            "first_interaction": min(e.timestamp for e in wallet_events).isoformat(),
            "last_interaction": max(e.timestamp for e in wallet_events).isoformat(),
            "chains_used": list(set(e.chain_id for e in wallet_events)),
            "event_types": list(set(e.event_name for e in wallet_events))
        })
    
    # Sort by interaction count
    wallet_details.sort(key=lambda x: x["interaction_count"], reverse=True)
    
    # Calculate summary metrics
    most_active_wallet = max(wallet_interactions.items(), key=lambda x: x[1])[0] if wallet_interactions else None
    most_active_chain = max(chain_interactions.items(), key=lambda x: x[1])[0] if chain_interactions else None
    
    return {
        "contract_address": contract_address,
        "total_interactions": len(contract_events),
        "unique_wallets": len(unique_wallets),
        "total_amount": total_amount,
        "chains_used": list(chains_used),
        "wallet_interactions": wallet_details[:50],  # Top 50 most active wallets
        "summary": {
            "first_interaction": min(e.timestamp for e in contract_events).isoformat(),
            "last_interaction": max(e.timestamp for e in contract_events).isoformat(),
            "most_active_wallet": most_active_wallet,
            "most_active_chain": most_active_chain,
            "avg_amount_per_interaction": round(total_amount / len(contract_events), 4) if contract_events else 0,
            "avg_interactions_per_wallet": round(len(contract_events) / len(unique_wallets), 2) if unique_wallets else 0
        }
    }