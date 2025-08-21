#!/usr/bin/env python3
"""
PostgreSQL Migration script to add region tracking columns.
Designed for Heroku PostgreSQL deployment.
"""

import os
import psycopg2
import logging
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection from DATABASE_URL."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return None
    
    try:
        parsed = urlparse(database_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password
        )
        conn.autocommit = False
        return conn
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        return None

def migrate_database():
    """Add region tracking columns."""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Check existing columns
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'events' AND table_schema = 'public'")
        events_columns = [col[0] for col in cursor.fetchall()]
        
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'web3_events' AND table_schema = 'public'")
        web3_events_columns = [col[0] for col in cursor.fetchall()]
        
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'platform_metrics' AND table_schema = 'public'")
        platform_metrics_columns = [col[0] for col in cursor.fetchall()]
        
        # Add to events table
        if 'country' not in events_columns:
            logger.info("Adding region columns to events table...")
            cursor.execute("ALTER TABLE events ADD COLUMN country VARCHAR(2)")
            cursor.execute("ALTER TABLE events ADD COLUMN region VARCHAR(100)")
            cursor.execute("ALTER TABLE events ADD COLUMN city VARCHAR(100)")
            cursor.execute("ALTER TABLE events ADD COLUMN ip_address VARCHAR(45)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_country ON events(country)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_region ON events(region)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_city ON events(city)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_ip ON events(ip_address)")
            logger.info("✓ Added region columns to events table")
        
        # Add to web3_events table
        if 'country' not in web3_events_columns:
            logger.info("Adding region columns to web3_events table...")
            cursor.execute("ALTER TABLE web3_events ADD COLUMN country VARCHAR(2)")
            cursor.execute("ALTER TABLE web3_events ADD COLUMN region VARCHAR(100)")
            cursor.execute("ALTER TABLE web3_events ADD COLUMN city VARCHAR(100)")
            cursor.execute("ALTER TABLE web3_events ADD COLUMN ip_address VARCHAR(45)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_web3_events_country ON web3_events(country)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_web3_events_region ON web3_events(region)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_web3_events_city ON web3_events(city)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_web3_events_ip ON web3_events(ip_address)")
            logger.info("✓ Added region columns to web3_events table")
        
        # Add to platform_metrics table
        if 'country' not in platform_metrics_columns:
            logger.info("Adding region columns to platform_metrics table...")
            cursor.execute("ALTER TABLE platform_metrics ADD COLUMN country VARCHAR(2)")
            cursor.execute("ALTER TABLE platform_metrics ADD COLUMN region VARCHAR(100)")
            cursor.execute("ALTER TABLE platform_metrics ADD COLUMN city VARCHAR(100)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_platform_metrics_country ON platform_metrics(country)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_platform_metrics_region ON platform_metrics(region)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_platform_metrics_city ON platform_metrics(city)")
            logger.info("✓ Added region columns to platform_metrics table")
        
        conn.commit()
        logger.info("✓ Migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    logger.info("Starting PostgreSQL region tracking migration...")
    if migrate_database():
        logger.info("Migration completed successfully!")
    else:
        logger.error("Migration failed!")
        exit(1)
