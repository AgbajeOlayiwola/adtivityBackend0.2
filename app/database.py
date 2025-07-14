# database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Configuration - replace with your actual DB URL
SQLALCHEMY_DATABASE_URL = "postgresql://adtivity:adtivity@localhost/adtivity"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,  # Adjust based on your needs
    max_overflow=10,
    pool_pre_ping=True  # Helps with connection recycling
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()