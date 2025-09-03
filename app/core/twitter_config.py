"""Twitter API configuration and credentials."""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class TwitterSettings(BaseSettings):
    """Twitter API configuration settings."""
    
    # Twitter API v2 credentials
    TWITTER_BEARER_TOKEN: str = "AAAAAAAAAAAAAAAAAAAAACPE3wEAAAAAskoYrlgAREowhCyJLNNXyq2MBPM%3DTrRkZH4jbWXmvia43jFNpzFzHP1r7CB9ljokcr2n4JrOTEqdpe"
    TWITTER_API_KEY: str = "TGu0dn0Gv345OR6s7aVacuf3Z"
    TWITTER_API_SECRET: str = "Vdl2RoHDaPrFpomFe9kBX3qVVUyJrPQrGNpReZyx1jCUbHLeOM"
    TWITTER_ACCESS_TOKEN: str = "1562397620005646338-WcoLwEbCaTHOVgUmbgrp25MjVl525W"
    TWITTER_ACCESS_TOKEN_SECRET: str = "jTECooIpBa6pBAvFLAf4rZDMkL276buMGYRlNtLaduyOE"
    
    # App information
    TWITTER_APP_NAME: str = "1963165157540110336cyber_rado"
    
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
