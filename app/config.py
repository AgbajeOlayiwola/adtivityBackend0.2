# app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings class using Pydantic.
    Loads configuration from environment variables defined in the .env file.
    """
    # Use DATABASE_URL to match the variable name used in the database.py file.
    # Pydantic will automatically find a variable with this name in your .env file.
    DATABASE_URL: str

    # The rest of your settings can remain the same
    clickhouse_host: str = "localhost"
    redis_host: str = "localhost"
    secret_key: str = "your-very-secure-and-long-secret-key-that-you-should-change"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(
        # Pydantic will look for an environment file named '.env'
        env_file=".env",
        env_file_encoding="utf-8"
    )

# Create a single instance of the settings to be used throughout the application.
settings = Settings()
