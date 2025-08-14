"""Company-related CRUD operations."""

import secrets
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from ..models import ClientCompany
from .auth import get_password_hash


def create_client_company_with_api_key(
    db: Session,
    name: str,
    platform_user_id: int,
) -> Tuple[ClientCompany, str]:
    """Create a new client company with an API key."""
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


def get_client_company_by_id(db: Session, company_id: int) -> Optional[ClientCompany]:
    """Get a client company by ID."""
    return db.query(ClientCompany).filter(ClientCompany.id == company_id).first()


def get_client_company_by_name(db: Session, name: str) -> Optional[ClientCompany]:
    """Get a client company by name."""
    return db.query(ClientCompany).filter(ClientCompany.name == name).first()


def get_client_companies_by_platform_user(
    db: Session, platform_user_id: int
) -> list[ClientCompany]:
    """Get all client companies owned by a platform user."""
    return db.query(ClientCompany).filter(
        ClientCompany.platform_user_id == platform_user_id,
        ClientCompany.is_active == True
    ).all()


def regenerate_client_company_api_key(
    db: Session, company_id: int
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