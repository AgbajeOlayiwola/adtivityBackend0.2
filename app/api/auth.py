"""Authentication endpoints."""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, Header
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_password_hash, create_access_token, get_current_platform_user, revoke_token
from ..core.auth_security import auth_security_service
from ..core.security_decorators import rate_limit_by_user, rate_limit_by_ip, log_sensitive_operations
from .. import crud, schemas, models

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=schemas.PlatformUser, status_code=status.HTTP_201_CREATED)
@rate_limit_by_ip(requests_per_minute=5, requests_per_hour=20)
@log_sensitive_operations("user_registration")
async def register_platform_user(
    user_input: schemas.PlatformUserCreate,
    request: Request,
    db: Session = Depends(get_db)
) -> schemas.PlatformUser:
    """Register a new platform user for the Adtivity dashboard."""
    # Validate password strength
    is_valid, error_message = auth_security_service.validate_password_strength(user_input.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password does not meet requirements: {error_message}"
        )
    
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
@rate_limit_by_ip(requests_per_minute=10, requests_per_hour=100)
@log_sensitive_operations("user_login")
async def login_for_access_token(
    user_credentials: schemas.PlatformUserLogin,
    request: Request,
    db: Session = Depends(get_db)
) -> schemas.Token:
    """Authenticate a PlatformUser and return a JWT access token."""
    # Use enhanced security authentication
    platform_user = auth_security_service.authenticate_user_with_security(
        db, 
        email=user_credentials.email, 
        password=user_credentials.password,
        request=request
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


@router.post("/forgot-password")
@rate_limit_by_ip(requests_per_minute=3, requests_per_hour=10)
@log_sensitive_operations("password_reset_request")
async def forgot_password(
    reset_request: schemas.PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> dict:
    """Request a password reset for a user account."""
    # Generate password reset token
    token = auth_security_service.generate_password_reset_token(db, reset_request.email)
    
    # Always return success to prevent email enumeration
    # In production, you would send the token via email here
    return {
        "message": "If an account with this email exists, a password reset link has been sent.",
        "token": token  # In production, remove this and send via email
    }


@router.post("/reset-password")
@rate_limit_by_ip(requests_per_minute=3, requests_per_hour=10)
@log_sensitive_operations("password_reset_confirm")
async def reset_password(
    reset_confirm: schemas.PasswordResetConfirm,
    request: Request,
    db: Session = Depends(get_db)
) -> dict:
    """Reset password using a valid reset token."""
    success = auth_security_service.use_password_reset_token(
        db, reset_confirm.token, reset_confirm.new_password
    )
    
    if success:
        return {"message": "Password has been successfully reset"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to reset password"
        )


@router.post("/change-password")
@rate_limit_by_user(requests_per_minute=5, requests_per_hour=20)
@log_sensitive_operations("password_change")
async def change_password(
    password_change: schemas.PasswordChange,
    request: Request,
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> dict:
    """Change password for authenticated user."""
    success = auth_security_service.change_password(
        db, current_user, password_change.current_password, password_change.new_password
    )
    
    if success:
        return {"message": "Password has been successfully changed"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to change password"
        )


@router.get("/login-attempts")
@log_sensitive_operations("login_attempts_view")
async def get_login_attempts(
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
    hours: int = Query(default=24, ge=1, le=168, description="Hours to look back")
) -> dict:
    """Get login attempts summary for the current user."""
    summary = auth_security_service.get_login_attempts_summary(
        db, current_user.email, hours
    )
    
    return {
        "email": current_user.email,
        "summary": summary
    }


@router.post("/logout")
async def logout(
    authorization: str = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
    current_user: models.PlatformUser = Depends(get_current_platform_user)
):
    """Logout and revoke the current access token."""
    if not authorization:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization header missing")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Authorization header")

    token = parts[1]
    try:
        revoke_token(token=token, db=db, user_id=str(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to revoke token: {e}")

    return {"message": "Successfully logged out"}
