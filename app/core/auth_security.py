"""
Enhanced authentication security with login attempt tracking and password reset.
"""

import secrets
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from fastapi import HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from .security import get_password_hash, verify_password
from .. import models, crud

logger = logging.getLogger(__name__)

# Security configuration
MAX_LOGIN_ATTEMPTS = 5  # Maximum failed attempts before temporary lockout
LOCKOUT_DURATION_MINUTES = 15  # Lockout duration in minutes
PASSWORD_RESET_TOKEN_EXPIRY_HOURS = 24  # Password reset token expiry
MIN_PASSWORD_LENGTH = 8  # Minimum password length
PASSWORD_COMPLEXITY_REQUIRED = True  # Require password complexity

# Password complexity requirements
PASSWORD_REQUIREMENTS = {
    'min_length': 8,
    'require_uppercase': True,
    'require_lowercase': True,
    'require_digits': True,
    'require_special': True,
    'special_chars': '!@#$%^&*()_+-=[]{}|;:,.<>?'
}


class AuthSecurityService:
    """Service for handling authentication security."""
    
    def __init__(self):
        self.max_attempts = MAX_LOGIN_ATTEMPTS
        self.lockout_duration = timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        self.token_expiry = timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRY_HOURS)
    
    def validate_password_strength(self, password: str) -> Tuple[bool, str]:
        """
        Validate password strength according to requirements.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(password) < PASSWORD_REQUIREMENTS['min_length']:
            return False, f"Password must be at least {PASSWORD_REQUIREMENTS['min_length']} characters long"
        
        if PASSWORD_REQUIREMENTS['require_uppercase'] and not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        
        if PASSWORD_REQUIREMENTS['require_lowercase'] and not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        
        if PASSWORD_REQUIREMENTS['require_digits'] and not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit"
        
        if PASSWORD_REQUIREMENTS['require_special']:
            special_chars = PASSWORD_REQUIREMENTS['special_chars']
            if not any(c in special_chars for c in password):
                return False, f"Password must contain at least one special character ({special_chars})"
        
        return True, ""
    
    def is_account_locked(self, db: Session, email: str) -> Tuple[bool, Optional[datetime]]:
        """
        Check if an account is locked due to too many failed login attempts.
        
        Returns:
            Tuple of (is_locked, lockout_until)
        """
        # Get recent failed attempts
        cutoff_time = datetime.now(timezone.utc) - self.lockout_duration
        recent_failed_attempts = db.query(models.LoginAttempt).filter(
            and_(
                models.LoginAttempt.email == email,
                models.LoginAttempt.success == False,
                models.LoginAttempt.timestamp >= cutoff_time
            )
        ).count()
        
        if recent_failed_attempts >= self.max_attempts:
            # Calculate when the lockout expires
            oldest_failed_attempt = db.query(models.LoginAttempt).filter(
                and_(
                    models.LoginAttempt.email == email,
                    models.LoginAttempt.success == False,
                    models.LoginAttempt.timestamp >= cutoff_time
                )
            ).order_by(models.LoginAttempt.timestamp.desc()).first()
            
            if oldest_failed_attempt:
                lockout_until = oldest_failed_attempt.timestamp + self.lockout_duration
                return True, lockout_until
        
        return False, None
    
    def record_login_attempt(self, db: Session, email: str, ip_address: str, 
                           user_agent: str, success: bool) -> None:
        """Record a login attempt for security tracking."""
        try:
            login_attempt = models.LoginAttempt(
                email=email,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                timestamp=datetime.now(timezone.utc)
            )
            db.add(login_attempt)
            db.commit()
            
            if not success:
                logger.warning(f"Failed login attempt for {email} from {ip_address}")
            else:
                logger.info(f"Successful login for {email} from {ip_address}")
                
        except Exception as e:
            logger.error(f"Error recording login attempt: {e}")
            db.rollback()
    
    def get_client_ip(self, request: Request) -> str:
        """Extract client IP from request headers."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def authenticate_user_with_security(self, db: Session, email: str, password: str,
                                      request: Request) -> Optional[models.PlatformUser]:
        """
        Authenticate user with security measures.
        
        Returns:
            PlatformUser if authentication successful, None otherwise
        """
        ip_address = self.get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # Check if account is locked
        is_locked, lockout_until = self.is_account_locked(db, email)
        if is_locked:
            remaining_time = lockout_until - datetime.now(timezone.utc)
            minutes_remaining = int(remaining_time.total_seconds() / 60)
            
            logger.warning(f"Login attempt for locked account {email} from {ip_address}")
            self.record_login_attempt(db, email, ip_address, user_agent, False)
            
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account temporarily locked due to too many failed attempts. "
                       f"Please try again in {minutes_remaining} minutes."
            )
        
        # Attempt authentication
        user = crud.authenticate_platform_user(db, email=email, password=password)
        
        # Record the attempt
        self.record_login_attempt(db, email, ip_address, user_agent, user is not None)
        
        if user:
            # Update last login
            user.last_login = datetime.now(timezone.utc)
            db.commit()
            
            # Clear old failed attempts for this user
            self._clear_old_failed_attempts(db, email)
        
        return user
    
    def _clear_old_failed_attempts(self, db: Session, email: str) -> None:
        """Clear old failed login attempts for a user."""
        try:
            cutoff_time = datetime.now(timezone.utc) - self.lockout_duration
            db.query(models.LoginAttempt).filter(
                and_(
                    models.LoginAttempt.email == email,
                    models.LoginAttempt.success == False,
                    models.LoginAttempt.timestamp < cutoff_time
                )
            ).delete()
            db.commit()
        except Exception as e:
            logger.error(f"Error clearing old failed attempts: {e}")
            db.rollback()
    
    def generate_password_reset_token(self, db: Session, email: str) -> str:
        """
        Generate a password reset token for the given email.
        
        Returns:
            The reset token (not hashed)
        """
        # Check if user exists
        user = crud.get_platform_user_by_email(db, email=email)
        if not user:
            # Don't reveal if user exists or not
            return ""
        
        # Generate secure token
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Set expiry
        expires_at = datetime.now(timezone.utc) + self.token_expiry
        
        # Invalidate any existing tokens for this email
        db.query(models.PasswordResetToken).filter(
            models.PasswordResetToken.email == email
        ).delete()
        
        # Create new token
        reset_token = models.PasswordResetToken(
            email=email,
            token_hash=token_hash,
            expires_at=expires_at,
            used=False
        )
        
        db.add(reset_token)
        db.commit()
        
        logger.info(f"Password reset token generated for {email}")
        return token
    
    def validate_password_reset_token(self, db: Session, token: str) -> Optional[str]:
        """
        Validate a password reset token.
        
        Returns:
            Email address if token is valid, None otherwise
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Find token
        reset_token = db.query(models.PasswordResetToken).filter(
            and_(
                models.PasswordResetToken.token_hash == token_hash,
                models.PasswordResetToken.used == False,
                models.PasswordResetToken.expires_at > datetime.now(timezone.utc)
            )
        ).first()
        
        if reset_token:
            return reset_token.email
        
        return None
    
    def use_password_reset_token(self, db: Session, token: str, new_password: str) -> bool:
        """
        Use a password reset token to change password.
        
        Returns:
            True if successful, False otherwise
        """
        # Validate password strength
        is_valid, error_message = self.validate_password_strength(new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password does not meet requirements: {error_message}"
            )
        
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Find and validate token
        reset_token = db.query(models.PasswordResetToken).filter(
            and_(
                models.PasswordResetToken.token_hash == token_hash,
                models.PasswordResetToken.used == False,
                models.PasswordResetToken.expires_at > datetime.now(timezone.utc)
            )
        ).first()
        
        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token"
            )
        
        # Update user password
        user = crud.get_platform_user_by_email(db, email=reset_token.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found"
            )
        
        # Hash new password
        hashed_password = get_password_hash(new_password)
        user.hashed_password = hashed_password
        
        # Mark token as used
        reset_token.used = True
        
        # Clear old failed attempts for this user
        self._clear_old_failed_attempts(db, reset_token.email)
        
        db.commit()
        
        logger.info(f"Password reset completed for {reset_token.email}")
        return True
    
    def change_password(self, db: Session, user: models.PlatformUser, 
                       current_password: str, new_password: str) -> bool:
        """
        Change password for authenticated user.
        
        Returns:
            True if successful, False otherwise
        """
        # Verify current password
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Validate new password strength
        is_valid, error_message = self.validate_password_strength(new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password does not meet requirements: {error_message}"
            )
        
        # Check if new password is same as current
        if verify_password(new_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password"
            )
        
        # Update password
        user.hashed_password = get_password_hash(new_password)
        db.commit()
        
        logger.info(f"Password changed for user {user.email}")
        return True
    
    def get_login_attempts_summary(self, db: Session, email: str, 
                                 hours: int = 24) -> dict:
        """
        Get summary of login attempts for an email.
        
        Returns:
            Dictionary with attempt statistics
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        attempts = db.query(models.LoginAttempt).filter(
            and_(
                models.LoginAttempt.email == email,
                models.LoginAttempt.timestamp >= cutoff_time
            )
        ).all()
        
        total_attempts = len(attempts)
        successful_attempts = sum(1 for a in attempts if a.success)
        failed_attempts = total_attempts - successful_attempts
        
        # Check if account is currently locked
        is_locked, lockout_until = self.is_account_locked(db, email)
        
        return {
            "total_attempts": total_attempts,
            "successful_attempts": successful_attempts,
            "failed_attempts": failed_attempts,
            "is_locked": is_locked,
            "lockout_until": lockout_until.isoformat() if lockout_until else None,
            "time_period_hours": hours
        }


# Global instance
auth_security_service = AuthSecurityService()
