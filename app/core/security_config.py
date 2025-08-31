"""
Security configuration settings for the application.
"""

from dataclasses import dataclass
from typing import List

@dataclass
class SecurityConfig:
    """Security configuration settings."""
    
    # Rate limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000
    RATE_LIMIT_BURST_LIMIT: int = 10
    RATE_LIMIT_WINDOW_SIZE: int = 60  # seconds
    
    # Request limits
    MAX_REQUEST_SIZE_MB: int = 10
    MAX_CONCURRENT_REQUESTS: int = 100
    
    # IP blocking
    MAX_BLOCKED_REQUESTS_BEFORE_IP_BAN: int = 10
    IP_BAN_DURATION_MINUTES: int = 60
    SUSPICIOUS_REQUEST_BAN_DURATION_MINUTES: int = 30
    
    # Cleanup intervals
    CLEANUP_INTERVAL_SECONDS: int = 300  # 5 minutes
    METRICS_RETENTION_HOURS: int = 1
    
    # Suspicious patterns to block
    BLOCKED_USER_AGENTS: List[str] = None
    
    # API key security
    API_KEY_MIN_LENGTH: int = 32
    API_KEY_MAX_LENGTH: int = 128
    
    # JWT security
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password security
    MIN_PASSWORD_LENGTH: int = 8
    REQUIRE_PASSWORD_COMPLEXITY: bool = True
    
    # CORS settings
    ALLOWED_ORIGINS: List[str] = None
    ALLOW_CREDENTIALS: bool = True
    ALLOWED_METHODS: List[str] = None
    ALLOWED_HEADERS: List[str] = None
    
    def __post_init__(self):
        """Set default values for lists."""
        if self.BLOCKED_USER_AGENTS is None:
            self.BLOCKED_USER_AGENTS = [
                "bot", "crawler", "spider", "scraper",
                "sqlmap", "nikto", "nmap", "masscan",
                "curl/", "wget/", "python-requests/",
                "scanner", "probe", "attack"
            ]
        
        if self.ALLOWED_ORIGINS is None:
            self.ALLOWED_ORIGINS = [
                "http://localhost:3000",
                "http://localhost:8080",
                "https://yourdomain.com"
            ]
        
        if self.ALLOWED_METHODS is None:
            self.ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        
        if self.ALLOWED_HEADERS is None:
            self.ALLOWED_HEADERS = [
                "Authorization",
                "Content-Type",
                "X-API-Key",
                "X-Requested-With"
            ]

# Global security configuration
security_config = SecurityConfig()

# Environment-specific overrides
def get_security_config() -> SecurityConfig:
    """Get security configuration with environment overrides."""
    import os
    
    config = SecurityConfig()
    
    # Override with environment variables if present
    if os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE"):
        config.RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE"))
    
    if os.getenv("MAX_CONCURRENT_REQUESTS"):
        config.MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS"))
    
    if os.getenv("MAX_REQUEST_SIZE_MB"):
        config.MAX_REQUEST_SIZE_MB = int(os.getenv("MAX_REQUEST_SIZE_MB"))
    
    return config
