# app/database.py

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Import the settings from the core config file
from .core.config import settings

# This line now uses the settings object, which gets its value from the .env file
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# --- ADD THIS LOGIC HERE ---
# Heroku uses 'postgres' but SQLAlchemy needs 'postgresql'.
# This conditional check ensures the URL is always in the correct format.
if SQLALCHEMY_DATABASE_URL and SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace(
        "postgres://", "postgresql+psycopg2://", 1
    )
# --- END OF ADDED LOGIC ---

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
