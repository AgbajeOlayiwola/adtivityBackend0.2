"""Company-related CRUD operations."""

import secrets
import uuid
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session

from ..models import ClientCompany, CompanyTwitter, TeamMembership, TeamActivityLog
from .auth import get_password_hash


def create_client_company_with_api_key(
    db: Session,
    name: str,
    platform_user_id: uuid.UUID,
    campaign_url: Optional[str] = None,
) -> Tuple[ClientCompany, str]:
    """Create a new client company with an API key and basic subscription plan."""
    # Generate a secure API key
    api_key = secrets.token_urlsafe(32)
    api_key_hash = get_password_hash(api_key)
    
    db_company = ClientCompany(
        name=name,
        api_key_hash=api_key_hash,
        platform_user_id=platform_user_id,
        campaign_url=campaign_url,
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


def get_twitter_profile_by_platform_user(
    db: Session, platform_user_id: uuid.UUID
) -> Optional[CompanyTwitter]:
    """Get the first Twitter profile for companies owned by a platform user."""
    return (
        db.query(CompanyTwitter)
        .join(ClientCompany, CompanyTwitter.company_id == ClientCompany.id)
        .filter(
            ClientCompany.platform_user_id == platform_user_id,
            ClientCompany.is_active == True,
        )
        .first()
    )


# --- Team collaboration helpers ---


def log_team_activity(
    db: Session,
    *,
    company_id: uuid.UUID,
    user_id: Optional[uuid.UUID],
    action_type: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    meta: Optional[dict] = None,
) -> None:
    """Create a simple team activity log entry (no commit)."""
    activity = TeamActivityLog(
        company_id=company_id,
        user_id=user_id,
        action_type=action_type,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        meta=meta,
    )
    db.add(activity)


def ensure_owner_membership_for_company(db: Session, company: ClientCompany) -> None:
    """Ensure the owning platform user has an OWNER membership for this company."""
    existing = (
        db.query(TeamMembership)
        .filter(
            TeamMembership.company_id == company.id,
            TeamMembership.email == company.platform_user.email,
        )
        .first()
    )
    if existing:
        if existing.user_id is None:
            existing.user_id = company.platform_user_id
        if existing.role != "owner":
            existing.role = "owner"
        if existing.status != "active":
            existing.status = "active"
        return

    membership = TeamMembership(
        company_id=company.id,
        user_id=company.platform_user_id,
        email=company.platform_user.email,
        role="owner",
        status="active",
        invited_by_user_id=company.platform_user_id,
    )
    db.add(membership)


def create_team_invitation(
    db: Session,
    *,
    company: ClientCompany,
    inviter: "PlatformUser",
    email: str,
    role: str,
    expires_at: Optional["datetime"] = None,
) -> TeamMembership:
    """Create or refresh a team invitation for the given email."""
    from datetime import datetime, timedelta, timezone
    import secrets as _secrets

    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    role_norm = role.lower()

    membership = (
        db.query(TeamMembership)
        .filter(
            TeamMembership.company_id == company.id,
            TeamMembership.email == email,
        )
        .first()
    )

    invite_token = _secrets.token_urlsafe(32)

    if membership is None:
        membership = TeamMembership(
            company_id=company.id,
            email=email,
            role=role_norm,
            status="pending",
            invited_by_user_id=inviter.id,
            invite_token=invite_token,
            expires_at=expires_at,
        )
        db.add(membership)
    else:
        membership.role = role_norm
        membership.status = "pending"
        membership.invited_by_user_id = inviter.id
        membership.invite_token = invite_token
        membership.expires_at = expires_at

    log_team_activity(
        db,
        company_id=company.id,
        user_id=inviter.id,
        action_type="invite_sent",
        target_type="membership",
        target_id=membership.id,
        meta={"email": email, "role": role_norm},
    )

    db.commit()
    db.refresh(membership)
    return membership


def accept_team_invitation(
    db: Session,
    *,
    token: str,
    user: "PlatformUser",
) -> TeamMembership:
    """Accept an invitation by token and bind it to the given user."""
    from datetime import datetime, timezone

    membership = (
        db.query(TeamMembership)
        .filter(TeamMembership.invite_token == token)
        .first()
    )
    if not membership:
        raise ValueError("Invalid invitation token")

    if membership.expires_at and membership.expires_at < datetime.now(timezone.utc):
        raise ValueError("Invitation has expired")

    existing_active = (
        db.query(TeamMembership)
        .filter(
            TeamMembership.company_id == membership.company_id,
            TeamMembership.user_id == user.id,
            TeamMembership.status == "active",
        )
        .first()
    )
    if existing_active:
        return existing_active

    membership.user_id = user.id
    membership.email = user.email
    membership.status = "active"
    membership.invite_token = None

    log_team_activity(
        db,
        company_id=membership.company_id,
        user_id=user.id,
        action_type="invite_accepted",
        target_type="membership",
        target_id=membership.id,
        meta={"role": membership.role},
    )

    db.commit()
    db.refresh(membership)
    return membership


def list_team_members(db: Session, company_id: uuid.UUID) -> list[TeamMembership]:
    """List all team memberships for a given company."""
    return (
        db.query(TeamMembership)
        .filter(TeamMembership.company_id == company_id)
        .order_by(TeamMembership.created_at.asc())
        .all()
    )
