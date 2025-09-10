"""Company-related CRUD operations."""

import secrets
import uuid
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session

from ..models import ClientCompany, CompanyTwitter
from .auth import get_password_hash


def create_client_company_with_api_key(
    db: Session,
    name: str,
    platform_user_id: uuid.UUID,
) -> Tuple[ClientCompany, str]:
    """Create a new client company with an API key and basic subscription plan."""
    # Generate a secure API key
    api_key = secrets.token_urlsafe(32)
    api_key_hash = get_password_hash(api_key)
    
    db_company = ClientCompany(
        name=name,
        api_key_hash=api_key_hash,
        platform_user_id=platform_user_id,
    )
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    
    # Automatically create a basic subscription plan for the new company
    from ..models import SubscriptionPlan
    from datetime import datetime, timezone
    
    basic_plan = SubscriptionPlan(
        id=uuid.uuid4(),
        company_id=db_company.id,
        plan_tier=1,
        plan_name="basic",
        raw_data_retention_days=30,
        aggregation_frequency="daily",
        max_raw_events_per_month=1000,
        max_aggregated_rows_per_month=100000,
        monthly_price_usd=0.0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(basic_plan)
    db.commit()
    
    return db_company, api_key


def get_client_company_by_api_key(db: Session, api_key: str) -> Optional[ClientCompany]:
    """Get a client company by API key."""
    from .auth import verify_password
    
    # We need to check against all companies since we can't hash the input
    # This is not efficient for large numbers of companies
    # Consider using a more efficient method in production
    companies = db.query(ClientCompany).filter(ClientCompany.is_active == True).all()
    
    for company in companies:
        if verify_password(api_key, company.api_key_hash):
            return company
    
    return None


def get_client_company_by_id(db: Session, company_id: uuid.UUID) -> Optional[ClientCompany]:
    """Get a client company by ID."""
    return db.query(ClientCompany).filter(ClientCompany.id == company_id).first()


def get_client_company_by_name(db: Session, name: str) -> Optional[ClientCompany]:
    """Get a client company by name."""
    return db.query(ClientCompany).filter(ClientCompany.name == name).first()


def get_client_companies_by_platform_user(
    db: Session, platform_user_id: uuid.UUID
) -> list[ClientCompany]:
    """Get all client companies owned by a platform user."""
    return db.query(ClientCompany).filter(
        ClientCompany.platform_user_id == platform_user_id,
        ClientCompany.is_active == True
    ).all()


def regenerate_client_company_api_key(
    db: Session, company_id: uuid.UUID
) -> Tuple[ClientCompany, str]:
    """Regenerate API key for a client company."""
    company = get_client_company_by_id(db, company_id)
    if not company:
        raise ValueError("Company not found")
    
    # Generate new API key
    new_api_key = secrets.token_urlsafe(32)
    new_api_key_hash = get_password_hash(new_api_key)
    
    # Update company
    company.api_key_hash = new_api_key_hash
    db.commit()
    db.refresh(company)
    
    return company, new_api_key


def get_twitter_profiles_by_platform_user(
    db: Session, platform_user_id: uuid.UUID
) -> List[CompanyTwitter]:
    """Get all Twitter profiles for companies owned by a platform user."""
    return db.query(CompanyTwitter)\
        .join(ClientCompany, CompanyTwitter.company_id == ClientCompany.id)\
        .filter(
            ClientCompany.platform_user_id == platform_user_id,
            ClientCompany.is_active == True
        ).all()