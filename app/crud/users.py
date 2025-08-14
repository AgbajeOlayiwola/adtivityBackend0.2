"""User-related CRUD operations."""

from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import PlatformUser, ClientAppUser
from .auth import verify_password


def create_platform_user(
    db: Session,
    email: str,
    hashed_password: str,
    name: Optional[str] = None,
    phone_number: Optional[str] = None,
) -> PlatformUser:
    """Create a new platform user."""
    db_user = PlatformUser(
        email=email,
        hashed_password=hashed_password,
        name=name,
        phone_number=phone_number,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_platform_user_by_email(db: Session, email: str) -> Optional[PlatformUser]:
    """Get a platform user by email."""
    return db.query(PlatformUser).filter(
        func.lower(PlatformUser.email) == func.lower(email)
    ).first()


def get_platform_user_by_id(db: Session, user_id: int) -> Optional[PlatformUser]:
    """Get a platform user by ID."""
    return db.query(PlatformUser).filter(PlatformUser.id == user_id).first()


def authenticate_platform_user(db: Session, email: str, password: str) -> Optional[PlatformUser]:
    """Authenticate a platform user."""
    user = get_platform_user_by_email(db, email=email)
    if not user or not verify_password(password, user.hashed_password) or not user.is_active:
        return None
    return user


def create_client_app_user(
    db: Session,
    email: str,
    hashed_password: str,
    name: Optional[str] = None,
    country: Optional[str] = None,
    subscription_plan: str = "free",
    billing_id: Optional[str] = None,
    wallet_address: Optional[str] = None,
    wallet_type: Optional[str] = None,
) -> ClientAppUser:
    """Create a new client application user."""
    db_user = ClientAppUser(
        email=email,
        hashed_password=hashed_password,
        name=name,
        country=country,
        subscription_plan=subscription_plan,
        billing_id=billing_id,
        wallet_address=wallet_address,
        wallet_type=wallet_type,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_client_app_user(db: Session, user_id: int) -> Optional[ClientAppUser]:
    """Get a client app user by ID."""
    return db.query(ClientAppUser).filter(ClientAppUser.id == user_id).first()


def get_client_app_user_by_email(db: Session, email: str) -> Optional[ClientAppUser]:
    """Get a client app user by email."""
    return db.query(ClientAppUser).filter(
        func.lower(ClientAppUser.email) == func.lower(email)
    ).first()


def get_client_app_user_by_wallet(db: Session, wallet_address: str) -> Optional[ClientAppUser]:
    """Get a client app user by wallet address."""
    return db.query(ClientAppUser).filter(
        ClientAppUser.wallet_address == wallet_address
    ).first()


def update_client_app_user_verification(
    db: Session, user_id: int, is_verified: bool
) -> Optional[ClientAppUser]:
    """Update client app user verification status."""
    user = get_client_app_user(db, user_id)
    if user:
        user.is_verified = is_verified
        db.commit()
        db.refresh(user)
    return user


def upsert_client_app_user_from_sdk_event(
    db: Session,
    email: Optional[str] = None,
    wallet_address: Optional[str] = None,
    name: Optional[str] = None,
    country: Optional[str] = None,
) -> Optional[ClientAppUser]:
    """Create or update a client app user from SDK event data."""
    if not email and not wallet_address:
        return None
    
    # Try to find existing user
    user = None
    if email:
        user = get_client_app_user_by_email(db, email)
    if not user and wallet_address:
        user = get_client_app_user_by_wallet(db, wallet_address)
    
    if user:
        # Update existing user
        if name and not user.name:
            user.name = name
        if country and not user.country:
            user.country = country
        db.commit()
        db.refresh(user)
    else:
        # Create new user
        user = create_client_app_user(
            db=db,
            email=email or "",
            hashed_password="",  # No password for SDK-created users
            name=name,
            country=country,
        )
    
    return user 