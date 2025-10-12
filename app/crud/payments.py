"""CRUD operations for payment sessions."""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from datetime import datetime, timezone, timedelta
import uuid
from decimal import Decimal

from .. import models, schemas


def create_payment_session(
    db: Session,
    payment_data: schemas.PaymentSessionCreate,
    geolocation_data: Optional[Dict[str, Any]] = None
) -> models.PaymentSession:
    """Create a new payment session."""
    payment_session = models.PaymentSession(
        company_id=payment_data.company_id,
        user_id=payment_data.user_id,
        session_id=payment_data.session_id,
        payment_id=payment_data.payment_id,
        payment_status=payment_data.payment_status,
        payment_amount=payment_data.payment_amount,
        payment_currency=payment_data.payment_currency,
        payment_method=payment_data.payment_method,
        wallet_address=payment_data.wallet_address,
        chain_id=payment_data.chain_id,
        transaction_hash=payment_data.transaction_hash,
        contract_address=payment_data.contract_address,
        payment_started_at=payment_data.payment_started_at,
        payment_completed_at=payment_data.payment_completed_at,
        payment_failed_at=payment_data.payment_failed_at,
        page_url=payment_data.page_url,
        referrer=payment_data.referrer,
        user_agent=payment_data.user_agent,
        properties=payment_data.properties or {}
    )
    
    # Add geolocation data if provided
    if geolocation_data:
        payment_session.country = geolocation_data.get("country")
        payment_session.region = geolocation_data.get("region")
        payment_session.city = geolocation_data.get("city")
        payment_session.ip_address = geolocation_data.get("ip_address")
    
    db.add(payment_session)
    db.commit()
    db.refresh(payment_session)
    return payment_session


def get_payment_session(
    db: Session,
    payment_id: str
) -> Optional[models.PaymentSession]:
    """Get a payment session by payment ID."""
    return db.query(models.PaymentSession).filter(
        models.PaymentSession.payment_id == payment_id
    ).first()


def update_payment_session(
    db: Session,
    payment_id: str,
    update_data: schemas.PaymentSessionUpdate
) -> Optional[models.PaymentSession]:
    """Update a payment session."""
    payment_session = get_payment_session(db, payment_id)
    if not payment_session:
        return None
    
    # Update fields if provided
    for field, value in update_data.dict(exclude_unset=True).items():
        if field == "payment_status" and value == schemas.PaymentStatus.COMPLETED:
            # Set completion time when status changes to completed
            setattr(payment_session, field, value)
            if not payment_session.payment_completed_at:
                payment_session.payment_completed_at = datetime.now(timezone.utc)
        elif field == "payment_status" and value == schemas.PaymentStatus.FAILED:
            # Set failure time when status changes to failed
            setattr(payment_session, field, value)
            if not payment_session.payment_failed_at:
                payment_session.payment_failed_at = datetime.now(timezone.utc)
        else:
            setattr(payment_session, field, value)
    
    db.commit()
    db.refresh(payment_session)
    return payment_session


def get_payment_sessions_by_company(
    db: Session,
    company_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
    status_filter: Optional[str] = None,
    user_id: Optional[str] = None
) -> List[models.PaymentSession]:
    """Get payment sessions for a company with optional filtering."""
    query = db.query(models.PaymentSession).filter(
        models.PaymentSession.company_id == company_id
    )
    
    if status_filter:
        query = query.filter(models.PaymentSession.payment_status == status_filter)
    
    if user_id:
        query = query.filter(models.PaymentSession.user_id == user_id)
    
    return query.order_by(desc(models.PaymentSession.payment_started_at)).offset(offset).limit(limit).all()


def get_payment_analytics(
    db: Session,
    company_id: uuid.UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """Get payment analytics for a company."""
    query = db.query(models.PaymentSession).filter(
        models.PaymentSession.company_id == company_id
    )
    
    if start_date:
        query = query.filter(models.PaymentSession.payment_started_at >= start_date)
    if end_date:
        query = query.filter(models.PaymentSession.payment_started_at <= end_date)
    
    payments = query.all()
    
    if not payments:
        return {
            "total_payments": 0,
            "completed_payments": 0,
            "failed_payments": 0,
            "pending_payments": 0,
            "cancelled_payments": 0,
            "completion_rate": 0.0,
            "total_revenue": Decimal("0"),
            "average_payment_amount": Decimal("0"),
            "payment_methods_breakdown": {},
            "currency_breakdown": {},
            "chain_breakdown": {},
            "recent_payments": [],
            "conversion_funnel": {"started": 0, "completed": 0, "failed": 0}
        }
    
    # Calculate basic metrics
    total_payments = len(payments)
    completed_payments = len([p for p in payments if p.payment_status == "completed"])
    failed_payments = len([p for p in payments if p.payment_status == "failed"])
    pending_payments = len([p for p in payments if p.payment_status == "pending"])
    cancelled_payments = len([p for p in payments if p.payment_status == "cancelled"])
    
    completion_rate = (completed_payments / total_payments * 100) if total_payments > 0 else 0.0
    
    # Calculate revenue metrics
    completed_payments_with_amount = [p for p in payments if p.payment_status == "completed" and p.payment_amount]
    total_revenue = sum(p.payment_amount for p in completed_payments_with_amount) if completed_payments_with_amount else Decimal("0")
    average_payment_amount = total_revenue / len(completed_payments_with_amount) if completed_payments_with_amount else Decimal("0")
    
    # Breakdown by payment method
    payment_methods_breakdown = {}
    for payment in payments:
        if payment.payment_method:
            payment_methods_breakdown[payment.payment_method] = payment_methods_breakdown.get(payment.payment_method, 0) + 1
    
    # Breakdown by currency
    currency_breakdown = {}
    for payment in payments:
        if payment.payment_currency:
            currency_breakdown[payment.payment_currency] = currency_breakdown.get(payment.payment_currency, 0) + 1
    
    # Breakdown by chain
    chain_breakdown = {}
    for payment in payments:
        if payment.chain_id:
            chain_breakdown[payment.chain_id] = chain_breakdown.get(payment.chain_id, 0) + 1
    
    # Recent payments (last 10)
    recent_payments = sorted(payments, key=lambda x: x.payment_started_at, reverse=True)[:10]
    
    # Conversion funnel
    conversion_funnel = {
        "started": total_payments,
        "completed": completed_payments,
        "failed": failed_payments
    }
    
    return {
        "total_payments": total_payments,
        "completed_payments": completed_payments,
        "failed_payments": failed_payments,
        "pending_payments": pending_payments,
        "cancelled_payments": cancelled_payments,
        "completion_rate": completion_rate,
        "total_revenue": total_revenue,
        "average_payment_amount": average_payment_amount,
        "payment_methods_breakdown": payment_methods_breakdown,
        "currency_breakdown": currency_breakdown,
        "chain_breakdown": chain_breakdown,
        "recent_payments": recent_payments,
        "conversion_funnel": conversion_funnel
    }


def get_payment_sessions_by_user(
    db: Session,
    company_id: uuid.UUID,
    user_id: str,
    limit: int = 50
) -> List[models.PaymentSession]:
    """Get payment sessions for a specific user."""
    return db.query(models.PaymentSession).filter(
        and_(
            models.PaymentSession.company_id == company_id,
            models.PaymentSession.user_id == user_id
        )
    ).order_by(desc(models.PaymentSession.payment_started_at)).limit(limit).all()


def get_payment_sessions_by_session(
    db: Session,
    company_id: uuid.UUID,
    session_id: str
) -> List[models.PaymentSession]:
    """Get all payment sessions for a specific session."""
    return db.query(models.PaymentSession).filter(
        and_(
            models.PaymentSession.company_id == company_id,
            models.PaymentSession.session_id == session_id
        )
    ).order_by(desc(models.PaymentSession.payment_started_at)).all()


def get_pending_payments(
    db: Session,
    company_id: uuid.UUID,
    hours_threshold: int = 24
) -> List[models.PaymentSession]:
    """Get payments that have been pending for more than the threshold."""
    threshold_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)
    return db.query(models.PaymentSession).filter(
        and_(
            models.PaymentSession.company_id == company_id,
            models.PaymentSession.payment_status == "pending",
            models.PaymentSession.payment_started_at <= threshold_time
        )
    ).all()
