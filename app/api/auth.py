"""Authentication endpoints."""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_password_hash, create_access_token
from .. import crud, schemas

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=schemas.PlatformUser, status_code=status.HTTP_201_CREATED)
async def register_platform_user(
    user_input: schemas.PlatformUserCreate,
    db: Session = Depends(get_db)
) -> schemas.PlatformUser:
    """Register a new platform user for the Adtivity dashboard."""
    # Check if user already exists
    existing_user = crud.get_platform_user_by_email(db, email=user_input.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Platform user with this email already exists"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_input.password)
    db_user = crud.create_platform_user(
        db=db,
        email=user_input.email,
        hashed_password=hashed_password,
        name=user_input.name,
        phone_number=user_input.phone_number
    )
    
    return db_user


@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    user_credentials: schemas.PlatformUserLogin,
    db: Session = Depends(get_db)
) -> schemas.Token:
    """Authenticate a PlatformUser and return a JWT access token."""
    platform_user = crud.authenticate_platform_user(
        db, 
        email=user_credentials.email, 
        password=user_credentials.password
    )
    
    if not platform_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=30)  # Could be moved to settings
    access_token = create_access_token(
        data={"sub": str(platform_user.id)},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"} 