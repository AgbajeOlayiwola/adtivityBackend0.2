"""Twitter API configuration and credentials."""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class TwitterSettings(BaseSettings):
    """Twitter API configuration settings."""
    
    # Twitter API v2 credentials
    TWITTER_BEARER_TOKEN: str = "AAAAAAAAAAAAAAAAAAAAAGqI4gEAAAAA3Ax9fRumjjkVZcKO1NJAlLqAUW8%3Dj0ukJpi0Qw164KiUkPX5JBx8JgCgnGFVu8Aa2ZFCtkGNcKRApw"
    TWITTER_API_KEY: str = "sF90j2rPakrsdbLSjmYugj5CU"
    TWITTER_API_SECRET: str = "T56B3ULtwuYaXeXKbTFXRU4oOVeIyNVdc0YPs1rTMzr6wwokJh"
    TWITTER_ACCESS_TOKEN: str = "1918950441817149440-ZEPzdvI3L1MVuczEiDCbDqa7lnzIYR"
    TWITTER_ACCESS_TOKEN_SECRET: str = "qQHmKfCsXJwLWJGY8LhAe01LLeAeV0lWONY0rgkR2I5V1"
    
    # App information
    TWITTER_APP_NAME: str = "1975324211578314752UseAdtivity"
    
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
