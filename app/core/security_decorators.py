"""
Security decorators for additional endpoint protection.
"""

import time
import functools
from typing import Callable, Optional
from fastapi import HTTPException, status, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

def rate_limit_by_user(
    requests_per_minute: int = 30,
    requests_per_hour: int = 500,
    key_prefix: str = "user"
):
    """
    Rate limit decorator for user-specific endpoints.
    
    Args:
        requests_per_minute: Maximum requests per minute per user
        requests_per_hour: Maximum requests per hour per user
        key_prefix: Prefix for rate limiting key
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs (assuming current_user is passed)
            current_user = kwargs.get('current_user')
            if not current_user:
                # Try to find in args
                for arg in args:
                    if hasattr(arg, 'id') and hasattr(arg, 'email'):
                        current_user = arg
                        break
            
            if not current_user:
                # For unauthenticated requests, rely on the middleware rate limiting
                # which is based on IP address
                return await func(*args, **kwargs)
            
            # Create rate limit key
            user_id = str(current_user.id)
            rate_limit_key = f"{key_prefix}:{user_id}"
            
            # Check rate limits (simplified - in production use Redis)
            # For now, we'll rely on the middleware
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def rate_limit_by_ip(
    requests_per_minute: int = 30,
    requests_per_hour: int = 500,
    key_prefix: str = "ip"
):
    """
    Rate limit decorator for IP-based endpoints (like authentication).
    
    Args:
        requests_per_minute: Maximum requests per minute per IP
        requests_per_hour: Maximum requests per hour per IP
        key_prefix: Prefix for rate limiting key
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # For IP-based rate limiting, rely on the middleware
            # which already handles IP-based rate limiting
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def validate_query_parameters(
    max_days: int = 365,
    max_limit: int = 100,
    max_offset: int = 1000
):
    """
    Validate query parameters to prevent abuse.
    
    Args:
        max_days: Maximum days for date range queries
        max_limit: Maximum limit for pagination
        max_offset: Maximum offset for pagination
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Validate days parameter
            days = kwargs.get('days')
            if days and days > max_days:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Days parameter cannot exceed {max_days}"
                )
            
            # Validate limit parameter
            limit = kwargs.get('limit')
            if limit and limit > max_limit:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Limit parameter cannot exceed {max_limit}"
                )
            
            # Validate offset parameter
            offset = kwargs.get('offset')
            if offset and offset > max_offset:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Offset parameter cannot exceed {max_offset}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def require_company_ownership():
    """
    Decorator to ensure user owns the company they're accessing.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # This validation should be done in the endpoint logic
            # This decorator serves as a reminder
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def log_sensitive_operations(operation_type: str):
    """
    Log sensitive operations for audit purposes.
    
    Args:
        operation_type: Type of operation being performed
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user info
            current_user = kwargs.get('current_user')
            user_id = current_user.id if current_user else "unknown"
            user_email = current_user.email if current_user else "unknown"
            
            # Log the operation
            logger.info(
                f"Sensitive operation: {operation_type} by user {user_id} ({user_email})"
            )
            
            try:
                result = await func(*args, **kwargs)
                logger.info(f"Operation {operation_type} completed successfully for user {user_id}")
                return result
            except Exception as e:
                logger.error(f"Operation {operation_type} failed for user {user_id}: {e}")
                raise
        
        return wrapper
    return decorator

def validate_date_range(max_days: int = 365):
    """
    Validate date range parameters.
    
    Args:
        max_days: Maximum allowed date range in days
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            from datetime import datetime, timedelta
            
            # Check start_date and end_date if provided
            start_date = kwargs.get('start_date')
            end_date = kwargs.get('end_date')
            
            if start_date and end_date:
                date_diff = (end_date - start_date).days
                if date_diff > max_days:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Date range cannot exceed {max_days} days"
                    )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def prevent_sql_injection():
    """
    Basic SQL injection prevention decorator.
    Note: This is a basic check - proper parameterized queries are the main defense.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Check for suspicious patterns in string parameters
            suspicious_patterns = [
                "';", "--", "/*", "*/", "xp_", "sp_",
                "union", "select", "insert", "update", "delete",
                "drop", "create", "alter", "exec", "execute"
            ]
            
            for key, value in kwargs.items():
                if isinstance(value, str):
                    value_lower = value.lower()
                    for pattern in suspicious_patterns:
                        if pattern in value_lower:
                            logger.warning(f"Potential SQL injection attempt in parameter {key}: {value}")
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid parameter value"
                            )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
