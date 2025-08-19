#!/usr/bin/env python3
"""
Reset database with UUID-based tables for enhanced security.
This is a simpler approach for development environments.
"""

import os
import sys

# Set the database URL for PostgreSQL
os.environ['DATABASE_URL'] = 'postgresql://adtivity:adtivity123@localhost:5432/adtivity'

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.database import engine
    from app.models import Base
    
    print("Connecting to PostgreSQL database...")
    print("Dropping all existing tables...")
    
    # Drop all tables
    Base.metadata.drop_all(bind=engine, checkfirst=True)
    
    print("Creating new UUID-based tables...")
    
    # Create all tables with new UUID schema
    Base.metadata.create_all(bind=engine)
    
    print("Database reset successfully with UUID-based tables!")
    print("All identifiers now use UUIDs for enhanced security!")
    print("Database is ready!")
    
except Exception as e:
    print(f"Error resetting database: {e}")
    sys.exit(1)
