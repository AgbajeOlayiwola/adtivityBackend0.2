from pydantic_settings import BaseSettings 
from dotenv import load_dotenv  # For .env file support

load_dotenv()  # Load environment variables from .env file

class Settings(BaseSettings): 
    postgres_url: str = "postgresql://adtivity:adtivity123@localhost:5432/adtivity"
    clickhouse_host: str = "localhost"
    redis_host: str = "localhost"

    class Config:
        env_file = ".env"  # Override defaults with .env file

settings = Settings()  # Singleton instance