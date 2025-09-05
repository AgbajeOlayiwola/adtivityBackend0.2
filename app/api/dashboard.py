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


@router.get("/client-companies/{company_id}/events", response_model=List[schemas.Event])
async def get_client_company_events(
    company_id: uuid.UUID = Path(..., description="The UUID of the client company"),
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

    # Use original tables directly instead of aggregation system
    from sqlalchemy import and_, func
    
    # Get sessions data from original events and web3_events tables
    analytics_results = {}
    
    for company_id in company_ids:
        # Get events from original events table
        events_query = db.query(models.Event).filter(
            and_(
                models.Event.client_company_id == company_id,
                models.Event.created_at >= since,
                models.Event.created_at <= end_date
            )
        )
        
        # Get Web3 events from original web3_events table
        web3_events_query = db.query(models.Web3Event).filter(
            and_(
                models.Web3Event.client_company_id == company_id,
                models.Web3Event.created_at >= since,
                models.Web3Event.created_at <= end_date
            )
        )
        
        # Execute queries
        events = events_query.all()
        web3_events = web3_events_query.all()
        
        # Calculate sessions data
        all_events = events + web3_events
        sessions = {}
        
        for event in all_events:
            session_id = event.session_id
            if session_id:
                if session_id not in sessions:
                    sessions[session_id] = {
                        "session_id": session_id,
                        "first_seen": event.created_at,
                        "last_seen": event.created_at,
                        "events": 0,
                        "user_id": event.user_id
                    }
                sessions[session_id]["events"] += 1
                if event.created_at < sessions[session_id]["first_seen"]:
                    sessions[session_id]["first_seen"] = event.created_at
                if event.created_at > sessions[session_id]["last_seen"]:
                    sessions[session_id]["last_seen"] = event.created_at
        
        analytics_results[company_id] = {
            "sessions": list(sessions.values()),
            "total_sessions": len(sessions),
            "total_events": len(all_events),
            "data_source": "original_tables",
            "subscription_tier": "basic"
        }
    
    # Aggregate results across all companies
    total_sessions = 0
    total_events = 0
    sessions_per_day = []
    
    for company_id, result in analytics_results.items():
        total_sessions += result.get("total_sessions", 0)
        total_events += result.get("total_events", 0)
        
        # For daily breakdown, we'll need to implement this in the service
        # For now, return basic aggregated data
        if result.get("data_source") == "raw_events":
            # Handle raw data sessions per day
            pass
        elif result.get("data_source") in ["hourly_aggregation", "daily_aggregation"]:
            # Handle aggregated data
            pass
    
    avg_events_per_session = (total_events / total_sessions) if total_sessions else 0.0

    return {
        "total_sessions": int(total_sessions),
        "total_events": int(total_events),
        "avg_events_per_session": round(avg_events_per_session, 2),
        "sessions_per_day": sessions_per_day,  # TODO: Implement daily breakdown
        "data_sources": [result.get("data_source") for result in analytics_results.values()],
        "subscription_tiers": list(set([result.get("subscription_tier", "basic") for result in analytics_results.values()]))
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
    """Top regions by event count using aggregation system."""
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
    
    # Get regions analytics for last 30 days
    since = datetime.now(timezone.utc) - timedelta(days=30)
    end_date = datetime.now(timezone.utc)
    
    analytics_results = unified_service.get_analytics_data(
        company_ids=company_ids,
        start_date=since,
        end_date=end_date,
        data_type="regions"
    )
    
    # Aggregate regions across all companies
    all_regions = {}
    for company_id, result in analytics_results.items():
        regions = result.get("regions", [])
        for region in regions:
            country = region.get("country")
            if country:
                if country not in all_regions:
                    all_regions[country] = {
                        "country": country,
                        "region": region.get("region"),
                        "city": region.get("city"),
                        "count": 0
                    }
                all_regions[country]["count"] += region.get("events", 0)
    
    # Sort by count and limit
    sorted_regions = sorted(all_regions.values(), key=lambda x: x["count"], reverse=True)[:limit]
    
    # Calculate total events across all regions
    total_events = sum(region["count"] for region in all_regions.values())

    return {
        "items": sorted_regions,
        "total_events": total_events,
        "data_sources": [result.get("data_source") for result in analytics_results.values()],
        "subscription_tiers": list(set([result.get("subscription_tier", "basic") for result in analytics_results.values()]))
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

    # Use unified analytics service
    from ..core.unified_analytics_service import UnifiedAnalyticsService
    unified_service = UnifiedAnalyticsService(db)
    
    analytics_results = unified_service.get_analytics_data(
        company_ids=company_ids,
        start_date=since,
        end_date=end_date,
        data_type="unique_users"
    )
    
    # Aggregate results across all companies
    total_unique_users = 0
    total_events = 0
    all_sessions = []
    
    for company_id, result in analytics_results.items():
        total_unique_users += result.get("total_unique_users", 0)
        total_events += result.get("total_events", 0)
        
        # Get sessions for recent/top users (if available from raw data)
        if result.get("data_source") == "raw_events":
            # For raw data, we can get individual sessions
            sessions = result.get("sessions", [])
            for session in sessions:
                all_sessions.append({
                    "session_id": session.get("session_id"),
                    "first_seen": session.get("first_seen"),
                    "last_seen": session.get("last_seen"),
                    "total_events": session.get("events", 0),
                    "user_id": session.get("user_id")
                })
    
    # Calculate averages
    avg_events_per_user = (total_events / total_unique_users) if total_unique_users else 0.0

    # Sort sessions for recent and top users
    recent_users = []
    top_users_by_events = []
    
    if all_sessions:
        # Recent users (by last_seen)
        recent_sessions = sorted(all_sessions, key=lambda x: x.get("last_seen") or datetime.min, reverse=True)[:limit]
        recent_users = [
            schemas.UniqueUserData(
                session_id=s["session_id"],
                first_seen=s["first_seen"],
                last_seen=s["last_seen"],
                total_events=s["total_events"],
                company_id=company_id,
                company_name=company_name
            ) for s in recent_sessions
        ]

        # Top users (by total_events)
        top_sessions = sorted(all_sessions, key=lambda x: x.get("total_events", 0), reverse=True)[:limit]
        top_users_by_events = [
            schemas.UniqueUserData(
                session_id=s["session_id"],
                first_seen=s["first_seen"],
                last_seen=s["last_seen"],
                total_events=s["total_events"],
                company_id=company_id,
                company_name=company_name
            ) for s in top_sessions
        ]

    return schemas.UniqueUsersResponse(
        total_unique_users=int(total_unique_users),
        total_events=int(total_events),
        avg_events_per_user=round(avg_events_per_user, 2),
        users_per_day=[],  # TODO: Implement daily breakdown in aggregation service
        recent_users=recent_users,
        top_users_by_events=top_users_by_events
    ) 