# app/config.py
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists.
# This makes it easy to manage different settings for development and production.
load_dotenv()

class Settings(BaseSettings):
    """
    Application settings class using Pydantic BaseSettings.
    It loads configuration from environment variables, with defaults provided
    here for development. For production, you should set these in your
    environment or a .env file.
    """
    # Database connection strings
    postgres_url: str = "postgresql://adtivity:adtivity123@localhost:5432/adtivity"
    clickhouse_host: str = "localhost"
    redis_host: str = "localhost"

    # Security variables for JWT authentication
    # This should be a long, random string.
    # We provide a default, but it should be overridden in production.
    secret_key: str = "your-very-secure-and-long-secret-key-that-you-should-change"
    
    # The algorithm used for JWT signing.
    algorithm: str = "HS256"
    
    # The number of minutes before an access token expires.
    access_token_expire_minutes: int = 30

    class Config:
        # Pydantic will look for an environment file named '.env'
        env_file = ".env"

# Create a single instance of the settings to be used throughout the application.
settings = Settings()
