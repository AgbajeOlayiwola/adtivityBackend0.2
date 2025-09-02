"""Twitter API configuration and credentials."""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class TwitterSettings(BaseSettings):
    """Twitter API configuration settings."""
    
    # Twitter API v2 credentials
    TWITTER_BEARER_TOKEN: str = "AAAAAAAAAAAAAAAAAAAAAO5Y3wEAAAAATnNwLsV%2BdQ6IzWJAqBuSW0vneSQ%3DcGHoojRLv6T6mtPAjEZN9uCvtEBtvhr1my7LOkPLllgvG1DIFE"
    TWITTER_API_KEY: str = "1961451735949479936RadoGold57"
    TWITTER_API_SECRET: str = "ST6J6OxVcMsqRgcl3kUjIfkY7uellPhn4WG5gEUb6Fq4R"
    TWITTER_ACCESS_TOKEN: str = "987111107151192066-vrHvQOl2DTF1yZGpDee52wUuBRm7TsX"
    TWITTER_ACCESS_TOKEN_SECRET: str = "ST6J6OxVcMsqRgcl3kUjIfkY7uellPhn4WG5gEUb6Fq4R"
    
    # Twitter API endpoints
    TWITTER_API_BASE_URL: str = "https://api.twitter.com/2"
    TWITTER_USER_LOOKUP_URL: str = "https://api.twitter.com/2/users/by/username"
    TWITTER_USER_TWEETS_URL: str = "https://api.twitter.com/2/users/{user_id}/tweets"
    TWITTER_FOLLOWERS_URL: str = "https://api.twitter.com/2/users/{user_id}/followers"
    
    # Rate limiting
    TWITTER_RATE_LIMIT_WINDOW: int = 900  # 15 minutes
    TWITTER_MAX_REQUESTS_PER_WINDOW: int = 300  # 300 requests per 15 minutes
    
    # Cache settings
    TWITTER_CACHE_TTL: int = 300  # 5 minutes
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Allow extra fields from environment


# Global settings instance
twitter_settings = TwitterSettings()
