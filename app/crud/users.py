"""User-related CRUD operations."""

from typing import Optional
import uuid
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


def get_platform_user_by_id(db: Session, user_id: uuid.UUID) -> Optional[PlatformUser]:
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
    email: Optional[str] = None,
    hashed_password: Optional[str] = None,
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


def get_client_app_user(db: Session, user_id: uuid.UUID) -> Optional[ClientAppUser]:
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
    db: Session, user_id: uuid.UUID, is_verified: bool
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
        # Only create new user if we have a valid email or wallet address
        if email:
            user = create_client_app_user(
                db=db,
                email=email,
                hashed_password=None,  # No password for SDK-created users
                name=name,
                country=country,
            )
        elif wallet_address:
            user = create_client_app_user(
                db=db,
                email=None,
                hashed_password=None,  # No password for SDK-created users
                name=name,
                country=country,
                wallet_address=wallet_address,
            )
    
    return user


def get_user_by_wallet_address(db: Session, wallet_address: str) -> Optional[ClientAppUser]:
    """Get a user by wallet address (alias for get_client_app_user_by_wallet)."""
    return get_client_app_user_by_wallet(db, wallet_address)


def get_user_by_email(db: Session, email: str) -> Optional[ClientAppUser]:
    """Get a user by email (alias for get_client_app_user_by_email)."""
    return get_client_app_user_by_email(db, email)


def update_user_wallet_info(db: Session, user_id: uuid.UUID, wallet_data: dict) -> Optional[ClientAppUser]:
    """Update user wallet information."""
    user = get_client_app_user(db, user_id)
    if not user:
        return None
    
    # Update wallet-related fields
    if 'wallet_address' in wallet_data:
        user.wallet_address = wallet_data['wallet_address']
    if 'wallet_type' in wallet_data:
        user.wallet_type = wallet_data['wallet_type']
    if 'country' in wallet_data:
        user.country = wallet_data['country']
    if 'region' in wallet_data:
        user.region = wallet_data['region']
    if 'city' in wallet_data:
        user.city = wallet_data['city']
    
    db.commit()
    db.refresh(user)
    return user


def update_user_info(db: Session, user_id: uuid.UUID, user_data: dict) -> Optional[ClientAppUser]:
    """Update user information."""
    user = get_client_app_user(db, user_id)
    if not user:
        return None
    
    # Update user fields
    if 'name' in user_data:
        user.name = user_data['name']
    if 'phone_number' in user_data:
        user.phone_number = user_data['phone_number']
    if 'country' in user_data:
        user.country = user_data['country']
    if 'region' in user_data:
        user.region = user_data['region']
    if 'city' in user_data:
        user.city = user_data['city']
    if 'subscription_plan' in user_data:
        user.subscription_plan = user_data['subscription_plan']
    
    db.commit()
    db.refresh(user)
    return user


def create_wallet_user(db: Session, wallet_data: dict) -> ClientAppUser:
    """Create a new wallet user entry."""
    db_user = ClientAppUser(
        wallet_address=wallet_data['wallet_address'],
        wallet_type=wallet_data.get('wallet_type'),
        country=wallet_data.get('country'),
        region=wallet_data.get('region'),
        city=wallet_data.get('city'),
        company_id=wallet_data.get('company_id'),
        platform_user_id=wallet_data.get('platform_user_id'),
        user_id=wallet_data.get('user_id'),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def create_user(db: Session, user_data: dict) -> ClientAppUser:
    """Create a new user entry."""
    db_user = ClientAppUser(
        email=user_data['email'],
        name=user_data.get('name'),
        phone_number=user_data.get('phone_number'),
        country=user_data.get('country'),
        region=user_data.get('region'),
        city=user_data.get('city'),
        subscription_plan=user_data.get('subscription_plan'),
        company_id=user_data.get('company_id'),
        platform_user_id=user_data.get('platform_user_id'),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user 