"""
Security middleware for protecting against server overload and abuse.
"""

import time
import hashlib
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import asyncio
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10
    window_size: int = 60  # seconds

@dataclass
class RequestMetrics:
    """Track request metrics for rate limiting."""
    requests: deque = field(default_factory=lambda: deque())
    last_request: Optional[datetime] = None
    blocked_requests: int = 0

class SecurityMiddleware:
    """Security middleware for protecting against abuse and overload."""
    
    def __init__(self):
        self.rate_limit_config = RateLimitConfig()
        self.client_metrics: Dict[str, RequestMetrics] = defaultdict(RequestMetrics)
        self.suspicious_ips: Dict[str, datetime] = {}
        self.blocked_ips: Dict[str, datetime] = {}
        self.request_size_limit = 10 * 1024 * 1024  # 10MB
        self.max_concurrent_requests = 100
        self.current_requests = 0
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
        
        # Don't start cleanup task here - will be started when needed
    
    def get_client_identifier(self, request: Request) -> str:
        """Get unique identifier for client (IP + User-Agent hash)."""
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # Create hash of IP + User-Agent for better identification
        identifier = f"{client_ip}:{hashlib.md5(user_agent.encode()).hexdigest()[:8]}"
        return identifier
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request headers."""
        # Check for forwarded headers (common with proxies/load balancers)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct connection
        return request.client.host if request.client else "unknown"
    
    def is_rate_limited(self, client_id: str) -> Tuple[bool, Dict]:
        """Check if client is rate limited."""
        now = datetime.now()
        metrics = self.client_metrics[client_id]
        
        # Clean old requests outside the window
        window_start = now - timedelta(seconds=self.rate_limit_config.window_size)
        while metrics.requests and metrics.requests[0] < window_start:
            metrics.requests.popleft()
        
        # Check burst limit
        if len(metrics.requests) >= self.rate_limit_config.burst_limit:
            return True, {
                "reason": "burst_limit_exceeded",
                "limit": self.rate_limit_config.burst_limit,
                "current": len(metrics.requests)
            }
        
        # Check rate limits
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        
        requests_last_minute = sum(1 for req_time in metrics.requests if req_time > minute_ago)
        requests_last_hour = sum(1 for req_time in metrics.requests if req_time > hour_ago)
        
        if requests_last_minute > self.rate_limit_config.requests_per_minute:
            return True, {
                "reason": "rate_limit_exceeded",
                "period": "minute",
                "limit": self.rate_limit_config.requests_per_minute,
                "current": requests_last_minute
            }
        
        if requests_last_hour > self.rate_limit_config.requests_per_hour:
            return True, {
                "reason": "rate_limit_exceeded",
                "period": "hour",
                "limit": self.rate_limit_config.requests_per_hour,
                "current": requests_last_hour
            }
        
        return False, {}
    
    def record_request(self, client_id: str):
        """Record a successful request."""
        now = datetime.now()
        metrics = self.client_metrics[client_id]
        metrics.requests.append(now)
        metrics.last_request = now
    
    def is_ip_blocked(self, client_ip: str) -> bool:
        """Check if IP is blocked."""
        if client_ip in self.blocked_ips:
            block_until = self.blocked_ips[client_ip]
            if datetime.now() < block_until:
                return True
            else:
                # Unblock expired IPs
                del self.blocked_ips[client_ip]
        return False
    
    def block_ip(self, client_ip: str, duration_minutes: int = 60):
        """Block an IP address for specified duration."""
        block_until = datetime.now() + timedelta(minutes=duration_minutes)
        self.blocked_ips[client_ip] = block_until
        logger.warning(f"Blocked IP {client_ip} until {block_until}")
    
    def validate_request_size(self, request: Request) -> bool:
        """Validate request size is within limits."""
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                return size <= self.request_size_limit
            except ValueError:
                return False
        return True
    
    def validate_request_headers(self, request: Request) -> bool:
        """Validate request headers for suspicious patterns."""
        user_agent = request.headers.get("user-agent", "").lower()
        
        # Block common bot/attack patterns
        suspicious_patterns = [
            "bot", "crawler", "spider", "scraper",
            "sqlmap", "nikto", "nmap", "masscan",
            "curl/", "wget/", "python-requests/"
        ]
        
        for pattern in suspicious_patterns:
            if pattern in user_agent:
                return False
        
        return True
    
    async def check_concurrent_requests(self) -> bool:
        """Check if we can handle more concurrent requests."""
        return self.current_requests < self.max_concurrent_requests
    
    @asynccontextmanager
    async def track_request(self):
        """Context manager to track concurrent requests."""
        self.current_requests += 1
        try:
            yield
        finally:
            self.current_requests -= 1
    
    async def _periodic_cleanup(self):
        """Periodically clean up old metrics and blocked IPs."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_old_data()
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    async def _cleanup_old_data(self):
        """Clean up old metrics and expired blocks."""
        now = datetime.now()
        cutoff = now - timedelta(hours=1)
        
        # Clean old metrics
        expired_clients = []
        for client_id, metrics in self.client_metrics.items():
            if metrics.last_request and metrics.last_request < cutoff:
                expired_clients.append(client_id)
        
        for client_id in expired_clients:
            del self.client_metrics[client_id]
        
        # Clean expired blocks
        expired_blocks = []
        for ip, block_until in self.blocked_ips.items():
            if now > block_until:
                expired_blocks.append(ip)
        
        for ip in expired_blocks:
            del self.blocked_ips[ip]
        
        if expired_clients or expired_blocks:
            logger.info(f"Cleaned up {len(expired_clients)} clients and {len(expired_blocks)} blocks")

# Global security middleware instance
security_middleware = None

def get_security_middleware():
    """Get or create security middleware instance."""
    global security_middleware
    if security_middleware is None:
        security_middleware = SecurityMiddleware()
    return security_middleware

async def security_middleware_handler(request: Request, call_next):
    """FastAPI middleware handler for security checks."""
    middleware = get_security_middleware()
    client_ip = middleware._get_client_ip(request)
    client_id = middleware.get_client_identifier(request)
    
    # Allow CORS preflight requests to pass through without security checks
    if request.method == "OPTIONS":
        response = await call_next(request)
        return response
    
    # Check if IP is blocked
    if middleware.is_ip_blocked(client_ip):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "IP address is temporarily blocked",
                "error_code": "IP_BLOCKED"
            }
        )
    
    # Check concurrent requests
    if not await middleware.check_concurrent_requests():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Server is overloaded, please try again later",
                "error_code": "SERVER_OVERLOAD"
            }
        )
    
    # Validate request size
    if not middleware.validate_request_size(request):
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={
                "detail": "Request too large",
                "error_code": "REQUEST_TOO_LARGE"
            }
        )
    
    # Validate headers
    if not middleware.validate_request_headers(request):
        middleware.block_ip(client_ip, duration_minutes=30)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "Request blocked due to suspicious headers",
                "error_code": "SUSPICIOUS_REQUEST"
            }
        )
    
    # Check rate limiting
    is_limited, limit_info = middleware.is_rate_limited(client_id)
    if is_limited:
        # Increment blocked requests counter
        middleware.client_metrics[client_id].blocked_requests += 1
        
        # Block IP if too many blocked requests
        if middleware.client_metrics[client_id].blocked_requests >= 10:
            middleware.block_ip(client_ip, duration_minutes=60)
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "Rate limit exceeded",
                "error_code": "RATE_LIMIT_EXCEEDED",
                "limit_info": limit_info
            }
        )
    
    # Track the request
    async with middleware.track_request():
        try:
            response = await call_next(request)
            middleware.record_request(client_id)
            return response
        except Exception as e:
            logger.error(f"Request processing error: {e}")
            raise
