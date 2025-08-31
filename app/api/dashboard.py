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
        company_ids = [company_id]
    else:
        company_ids = [c.id for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
        if not company_ids:
            return {"total_sessions": 0, "avg_events_per_session": 0.0, "sessions_per_day": []}

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Total sessions (distinct session_id, non-empty)
    total_sessions = db.query(func.count(func.distinct(models.Event.session_id))).filter(
        models.Event.client_company_id.in_(company_ids),
        models.Event.timestamp >= since,
        models.Event.session_id.isnot(None),
        models.Event.session_id != ""
    ).scalar() or 0

    # Average events per session
    events_count = db.query(func.count(models.Event.id)).filter(
        models.Event.client_company_id.in_(company_ids),
        models.Event.timestamp >= since
    ).scalar() or 0
    avg_events_per_session = (events_count / total_sessions) if total_sessions else 0.0

    # Sessions per day
    rows = db.query(
        func.date(models.Event.timestamp).label("day"),
        func.count(func.distinct(models.Event.session_id)).label("sessions")
    ).filter(
        models.Event.client_company_id.in_(company_ids),
        models.Event.timestamp >= since,
        models.Event.session_id.isnot(None),
        models.Event.session_id != ""
    ).group_by(func.date(models.Event.timestamp)).order_by(func.date(models.Event.timestamp)).all()

    sessions_per_day = [{"day": r.day.isoformat(), "sessions": int(r.sessions)} for r in rows]

    return {
        "total_sessions": int(total_sessions),
        "avg_events_per_session": round(avg_events_per_session, 2),
        "sessions_per_day": sessions_per_day
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
    """Top regions by event count (country/region/city)."""
    # Resolve company IDs owned by user
    if company_id:
        company = crud.get_client_company_by_id(db, company_id=company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this company")
        company_ids = [company_id]
    else:
        company_ids = [c.id for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
        if not company_ids:
            return {"items": []}

    rows = db.query(
        models.Event.country,
        models.Event.region,
        models.Event.city,
        func.count(models.Event.id).label("count")
    ).filter(
        models.Event.client_company_id.in_(company_ids),
        models.Event.country.isnot(None),
        models.Event.region.isnot(None),
        models.Event.city.isnot(None)
    ).group_by(
        models.Event.country,
        models.Event.region,
        models.Event.city
    ).order_by(desc("count")).limit(limit).all()

    return {
        "items": [
            {
                "country": r.country,
                "region": r.region,
                "city": r.city,
                "count": int(r.count)
            } for r in rows
        ]
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
    """Recent sessions with first/last timestamps and event counts."""
    # Resolve company IDs owned by user
    if company_id:
        company = crud.get_client_company_by_id(db, company_id=company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this company")
        company_ids = [company_id]
    else:
        company_ids = [c.id for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
        if not company_ids:
            return {"items": []}

    # Subquery to aggregate per session
    subq = db.query(
        models.Event.session_id.label("session_id"),
        func.min(models.Event.timestamp).label("first_seen"),
        func.max(models.Event.timestamp).label("last_seen"),
        func.count(models.Event.id).label("events")
    ).filter(
        models.Event.client_company_id.in_(company_ids),
        models.Event.session_id.isnot(None),
        models.Event.session_id != ""
    ).group_by(models.Event.session_id).subquery()

    rows = db.query(subq).order_by(desc(subq.c.last_seen)).limit(limit).all()

    return {
        "items": [
            {
                "session_id": r.session_id,
                "first_seen": r.first_seen.isoformat() if r.first_seen else None,
                "last_seen": r.last_seen.isoformat() if r.last_seen else None,
                "events": int(r.events)
            } for r in rows
        ]
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
    """Get unique users analytics including total users, events per user, and recent activity."""
    # Resolve company IDs owned by user
    if company_id:
        company = crud.get_client_company_by_id(db, company_id=company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this company")
        company_ids = [company_id]
        company_name = company.name
    else:
        company_ids = [c.id for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
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

    # Total unique users (distinct session_id, non-empty)
    total_unique_users = db.query(func.count(func.distinct(models.Event.session_id))).filter(
        models.Event.client_company_id.in_(company_ids),
        models.Event.timestamp >= since,
        models.Event.session_id.isnot(None),
        models.Event.session_id != ""
    ).scalar() or 0

    # Total events
    total_events = db.query(func.count(models.Event.id)).filter(
        models.Event.client_company_id.in_(company_ids),
        models.Event.timestamp >= since
    ).scalar() or 0

    # Average events per user
    avg_events_per_user = (total_events / total_unique_users) if total_unique_users else 0.0

    # Users per day
    users_per_day_rows = db.query(
        func.date(models.Event.timestamp).label("day"),
        func.count(func.distinct(models.Event.session_id)).label("users")
    ).filter(
        models.Event.client_company_id.in_(company_ids),
        models.Event.timestamp >= since,
        models.Event.session_id.isnot(None),
        models.Event.session_id != ""
    ).group_by(func.date(models.Event.timestamp)).order_by(func.date(models.Event.timestamp)).all()

    users_per_day = [{"day": r.day.isoformat(), "users": int(r.users)} for r in users_per_day_rows]

    # Recent users (most recently active)
    recent_users_subq = db.query(
        models.Event.session_id.label("session_id"),
        func.min(models.Event.timestamp).label("first_seen"),
        func.max(models.Event.timestamp).label("last_seen"),
        func.count(models.Event.id).label("total_events")
    ).filter(
        models.Event.client_company_id.in_(company_ids),
        models.Event.session_id.isnot(None),
        models.Event.session_id != ""
    ).group_by(models.Event.session_id).subquery()

    recent_users_rows = db.query(recent_users_subq).order_by(desc(recent_users_subq.c.last_seen)).limit(limit).all()

    recent_users = [
        schemas.UniqueUserData(
            session_id=r.session_id,
            first_seen=r.first_seen,
            last_seen=r.last_seen,
            total_events=int(r.total_events),
            company_id=company_id,
            company_name=company_name
        ) for r in recent_users_rows
    ]

    # Top users by events
    top_users_rows = db.query(recent_users_subq).order_by(desc(recent_users_subq.c.total_events)).limit(limit).all()

    top_users_by_events = [
        schemas.UniqueUserData(
            session_id=r.session_id,
            first_seen=r.first_seen,
            last_seen=r.last_seen,
            total_events=int(r.total_events),
            company_id=company_id,
            company_name=company_name
        ) for r in top_users_rows
    ]

    return schemas.UniqueUsersResponse(
        total_unique_users=int(total_unique_users),
        total_events=int(total_events),
        avg_events_per_user=round(avg_events_per_user, 2),
        users_per_day=users_per_day,
        recent_users=recent_users,
        top_users_by_events=top_users_by_events
    ) 