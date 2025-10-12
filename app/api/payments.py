"""Payment session management API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
import uuid

from ..core.database import get_db
from ..core.security import get_current_platform_user
from ..core.security_decorators import rate_limit_by_user
from ..core.security_decorators import log_sensitive_operations
from .. import crud, schemas, models

router = APIRouter(prefix="/payments", tags=["Payment Sessions"])


@router.get("/sessions", response_model=List[schemas.PaymentSessionResponse])
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@log_sensitive_operations("list_payment_sessions")
async def get_payment_sessions(
    company_id: uuid.UUID = Query(..., description="Company ID"),
    status: Optional[str] = Query(None, description="Filter by payment status"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(100, ge=1, le=1000, description="Number of sessions to return"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get payment sessions for a company with optional filtering."""
    # Verify user has access to the company
    company = crud.get_client_company_by_id(db, company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this company")
    
    sessions = crud.payments.get_payment_sessions_by_company(
        db, company_id, limit, offset, status, user_id
    )
    
    return [schemas.PaymentSessionResponse.from_orm(session) for session in sessions]


@router.get("/sessions/{payment_id}", response_model=schemas.PaymentSessionResponse)
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@log_sensitive_operations("get_payment_session")
async def get_payment_session(
    payment_id: str = Path(..., description="Payment ID"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get a specific payment session by payment ID."""
    session = crud.payments.get_payment_session(db, payment_id)
    if not session:
        raise HTTPException(status_code=404, detail="Payment session not found")
    
    # Verify user has access to the company
    company = crud.get_client_company_by_id(db, session.company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this payment session")
    
    return schemas.PaymentSessionResponse.from_orm(session)


@router.patch("/sessions/{payment_id}", response_model=schemas.PaymentSessionResponse)
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@log_sensitive_operations("update_payment_session")
async def update_payment_session(
    payment_id: str = Path(..., description="Payment ID"),
    update_data: schemas.PaymentSessionUpdate = ...,
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Update a payment session status and details."""
    # First get the session to verify access
    session = crud.payments.get_payment_session(db, payment_id)
    if not session:
        raise HTTPException(status_code=404, detail="Payment session not found")
    
    # Verify user has access to the company
    company = crud.get_client_company_by_id(db, session.company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this payment session")
    
    updated_session = crud.payments.update_payment_session(db, payment_id, update_data)
    if not updated_session:
        raise HTTPException(status_code=400, detail="Failed to update payment session")
    
    return schemas.PaymentSessionResponse.from_orm(updated_session)


@router.get("/analytics", response_model=schemas.PaymentAnalyticsResponse)
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@log_sensitive_operations("payment_analytics")
async def get_payment_analytics(
    company_id: uuid.UUID = Query(..., description="Company ID"),
    start_date: Optional[datetime] = Query(None, description="Start date for analytics"),
    end_date: Optional[datetime] = Query(None, description="End date for analytics"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get payment analytics for a company."""
    # Verify user has access to the company
    company = crud.get_client_company_by_id(db, company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this company")
    
    analytics = crud.payments.get_payment_analytics(db, company_id, start_date, end_date)
    
    # Convert recent payments to response format
    analytics["recent_payments"] = [
        schemas.PaymentSessionResponse.from_orm(payment) 
        for payment in analytics["recent_payments"]
    ]
    
    return schemas.PaymentAnalyticsResponse(**analytics)


@router.get("/sessions/user/{user_id}", response_model=List[schemas.PaymentSessionResponse])
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@log_sensitive_operations("get_user_payment_sessions")
async def get_user_payment_sessions(
    company_id: uuid.UUID = Query(..., description="Company ID"),
    user_id: str = Path(..., description="User ID"),
    limit: int = Query(50, ge=1, le=500, description="Number of sessions to return"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get payment sessions for a specific user."""
    # Verify user has access to the company
    company = crud.get_client_company_by_id(db, company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this company")
    
    sessions = crud.payments.get_payment_sessions_by_user(db, company_id, user_id, limit)
    
    return [schemas.PaymentSessionResponse.from_orm(session) for session in sessions]


@router.get("/sessions/session/{session_id}", response_model=List[schemas.PaymentSessionResponse])
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@log_sensitive_operations("get_session_payments")
async def get_session_payments(
    company_id: uuid.UUID = Query(..., description="Company ID"),
    session_id: str = Path(..., description="Session ID"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get all payment sessions for a specific session."""
    # Verify user has access to the company
    company = crud.get_client_company_by_id(db, company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this company")
    
    sessions = crud.payments.get_payment_sessions_by_session(db, company_id, session_id)
    
    return [schemas.PaymentSessionResponse.from_orm(session) for session in sessions]


@router.get("/pending", response_model=List[schemas.PaymentSessionResponse])
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@log_sensitive_operations("get_pending_payments")
async def get_pending_payments(
    company_id: uuid.UUID = Query(..., description="Company ID"),
    hours_threshold: int = Query(24, ge=1, le=168, description="Hours threshold for pending payments"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get payments that have been pending for more than the threshold."""
    # Verify user has access to the company
    company = crud.get_client_company_by_id(db, company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this company")
    
    sessions = crud.payments.get_pending_payments(db, company_id, hours_threshold)
    
    return [schemas.PaymentSessionResponse.from_orm(session) for session in sessions]


@router.get("/conversion-funnel", response_model=dict)
@rate_limit_by_user(requests_per_minute=30, requests_per_hour=500)
@log_sensitive_operations("payment_conversion_funnel")
async def get_payment_conversion_funnel(
    company_id: uuid.UUID = Query(..., description="Company ID"),
    start_date: Optional[datetime] = Query(None, description="Start date for funnel analysis"),
    end_date: Optional[datetime] = Query(None, description="End date for funnel analysis"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get payment conversion funnel analysis."""
    # Verify user has access to the company
    company = crud.get_client_company_by_id(db, company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this company")
    
    analytics = crud.payments.get_payment_analytics(db, company_id, start_date, end_date)
    
    # Calculate conversion rates
    funnel = analytics["conversion_funnel"]
    total_started = funnel["started"]
    
    if total_started == 0:
        return {
            "conversion_funnel": funnel,
            "conversion_rates": {
                "started_to_completed": 0.0,
                "started_to_failed": 0.0,
                "completion_rate": 0.0
            }
        }
    
    started_to_completed = (funnel["completed"] / total_started) * 100
    started_to_failed = (funnel["failed"] / total_started) * 100
    completion_rate = (funnel["completed"] / total_started) * 100
    
    return {
        "conversion_funnel": funnel,
        "conversion_rates": {
            "started_to_completed": round(started_to_completed, 2),
            "started_to_failed": round(started_to_failed, 2),
            "completion_rate": round(completion_rate, 2)
        }
    }
