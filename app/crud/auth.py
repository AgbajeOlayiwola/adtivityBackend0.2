"""Authentication-related CRUD operations."""

from passlib.context import CryptContext
import bcrypt

# Password hashing context with explicit bcrypt backend
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__default_rounds=12,
    bcrypt__default_ident="2b"
)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt (max 72 bytes)."""
    # Ensure password doesn't exceed bcrypt's 72-byte limit
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return pwd_context.hash(password_bytes.decode('utf-8', errors='ignore'))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash (max 72 bytes)."""
    try:
        # Ensure password doesn't exceed bcrypt's 72-byte limit
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        return pwd_context.verify(password_bytes.decode('utf-8', errors='ignore'), hashed_password)
    except Exception:
        # If verification fails for any reason, return False
        return False 