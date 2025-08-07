import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Handle Heroku's DATABASE_URL and local development
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    # Fallback to SQLite for local development
    DATABASE_URL = "sqlite:///./ad-platform.db"
elif DATABASE_URL.startswith("postgres://"):
    # SQLAlchemy 1.4+ requires postgresql://
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Connection pool settings optimized for Heroku
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"sslmode": "require"} if DATABASE_URL.startswith("postgresql") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# FastAPI dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()