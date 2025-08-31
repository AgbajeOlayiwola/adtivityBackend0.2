#!/usr/bin/env python3
"""
SQLAlchemy-based migration script to add security tables.
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_security_tables():
    """Create security tables using SQLAlchemy."""
    
    # Get DATABASE_URL from config
    try:
        from app.core.config import settings
        database_url = settings.DATABASE_URL
        logger.info(f"Using DATABASE_URL from config")
    except Exception as e:
        logger.error(f"Failed to get DATABASE_URL from config: {e}")
        sys.exit(1)
    
    logger.info(f"Connecting to database...")
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Check if tables exist
            result = conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('login_attempts', 'password_reset_tokens')
            """))
            existing_tables = [row[0] for row in result.fetchall()]
            
            # Create login_attempts table
            if 'login_attempts' not in existing_tables:
                logger.info("Creating login_attempts table...")
                conn.execute(text("""
                    CREATE TABLE login_attempts (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        email VARCHAR NOT NULL,
                        ip_address VARCHAR NOT NULL,
                        user_agent VARCHAR,
                        success BOOLEAN DEFAULT FALSE,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Create indexes
                conn.execute(text("""
                    CREATE INDEX idx_login_attempts_email_timestamp 
                    ON login_attempts(email, timestamp)
                """))
                
                conn.execute(text("""
                    CREATE INDEX idx_login_attempts_ip_timestamp 
                    ON login_attempts(ip_address, timestamp)
                """))
                
                logger.info("✅ login_attempts table created successfully")
            else:
                logger.info("✅ login_attempts table already exists")
            
            # Create password_reset_tokens table
            if 'password_reset_tokens' not in existing_tables:
                logger.info("Creating password_reset_tokens table...")
                conn.execute(text("""
                    CREATE TABLE password_reset_tokens (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        email VARCHAR NOT NULL,
                        token_hash VARCHAR NOT NULL UNIQUE,
                        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        used BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Create indexes
                conn.execute(text("""
                    CREATE INDEX idx_password_reset_email_expires 
                    ON password_reset_tokens(email, expires_at)
                """))
                
                conn.execute(text("""
                    CREATE INDEX idx_password_reset_token_hash 
                    ON password_reset_tokens(token_hash)
                """))
                
                logger.info("✅ password_reset_tokens table created successfully")
            else:
                logger.info("✅ password_reset_tokens table already exists")
            
            conn.commit()
            logger.info("🎉 Security tables migration completed successfully!")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    logger.info("🔒 Starting security tables migration...")
    create_security_tables()
