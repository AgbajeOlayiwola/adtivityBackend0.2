"""Application configuration using Pydantic settings."""

from typing import Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Database Configuration
    DATABASE_URL: str = Field(default="postgresql://postgres:password@localhost:5432/adtivity", description="Database connection URL (defaults to local PostgreSQL)")
    
    # Security Configuration
    SECRET_KEY: str = Field(
        default="your-very-secure-and-long-secret-key-that-you-should-change-in-production",
        description="Secret key for JWT token signing"
    )
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="JWT token expiration time")
    
    # Redis Configuration
    REDIS_HOST: str = Field(default="localhost", description="Redis server host")
    REDIS_PORT: int = Field(default=6379, description="Redis server port")
    REDIS_DB: int = Field(default=0, description="Redis database number")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis password")
    
    # ClickHouse Configuration
    CLICKHOUSE_HOST: str = Field(default="localhost", description="ClickHouse server host")
    CLICKHOUSE_PORT: int = Field(default=8123, description="ClickHouse HTTP port")
    CLICKHOUSE_DB: str = Field(default="default", description="ClickHouse database name")
    
    # Application Configuration
    APP_NAME: str = Field(default="Adtivity API", description="Application name")
    APP_VERSION: str = Field(default="0.1.0", description="Application version")
    DEBUG: bool = Field(default=False, description="Debug mode")
    
    # CORS Configuration
    CORS_ORIGINS: list[str] = Field(default=["*"], description="Allowed CORS origins")
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True, description="Allow CORS credentials")
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="Rate limit per minute per IP")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL is properly formatted."""
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg2://", 1)
        return v
    
    @validator("SECRET_KEY")
    def validate_secret_key(cls, v: str) -> str:
        """Ensure secret key is secure."""
        # Allow the default key in development
        if v == "your-very-secure-and-long-secret-key-that-you-should-change-in-production":
            return v
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        return v


# Global settings instance
settings = Settings() 