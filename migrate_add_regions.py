#!/usr/bin/env python3
"""
Migration script to add region tracking columns to existing tables.
This script adds country, region, city, and ip_address columns to the events, web3_events, and platform_metrics tables.
"""

import sqlite3
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """Add region tracking columns to the database."""
    db_path = Path("ad-platform.db")
    
    if not db_path.exists():
        logger.error("Database file not found: ad-platform.db")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(events)")
        events_columns = [column[1] for column in cursor.fetchall()]
        
        cursor.execute("PRAGMA table_info(web3_events)")
        web3_events_columns = [column[1] for column in cursor.fetchall()]
        
        cursor.execute("PRAGMA table_info(platform_metrics)")
        platform_metrics_columns = [column[1] for column in cursor.fetchall()]
        
        # Add columns to events table
        if 'country' not in events_columns:
            logger.info("Adding region columns to events table...")
            cursor.execute("ALTER TABLE events ADD COLUMN country TEXT")
            cursor.execute("ALTER TABLE events ADD COLUMN region TEXT")
            cursor.execute("ALTER TABLE events ADD COLUMN city TEXT")
            cursor.execute("ALTER TABLE events ADD COLUMN ip_address TEXT")
            
            # Create indexes for better query performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_country ON events(country)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_region ON events(region)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_city ON events(city)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_ip ON events(ip_address)")
            logger.info("✓ Added region columns to events table")
        else:
            logger.info("✓ Region columns already exist in events table")
        
        # Add columns to web3_events table
        if 'country' not in web3_events_columns:
            logger.info("Adding region columns to web3_events table...")
            cursor.execute("ALTER TABLE web3_events ADD COLUMN country TEXT")
            cursor.execute("ALTER TABLE web3_events ADD COLUMN region TEXT")
            cursor.execute("ALTER TABLE web3_events ADD COLUMN city TEXT")
            cursor.execute("ALTER TABLE web3_events ADD COLUMN ip_address TEXT")
            
            # Create indexes for better query performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_web3_events_country ON web3_events(country)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_web3_events_region ON web3_events(region)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_web3_events_city ON web3_events(city)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_web3_events_ip ON web3_events(ip_address)")
            logger.info("✓ Added region columns to web3_events table")
        else:
            logger.info("✓ Region columns already exist in web3_events table")
        
        # Add columns to platform_metrics table
        if 'country' not in platform_metrics_columns:
            logger.info("Adding region columns to platform_metrics table...")
            cursor.execute("ALTER TABLE platform_metrics ADD COLUMN country TEXT")
            cursor.execute("ALTER TABLE platform_metrics ADD COLUMN region TEXT")
            cursor.execute("ALTER TABLE platform_metrics ADD COLUMN city TEXT")
            
            # Create indexes for better query performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_platform_metrics_country ON platform_metrics(country)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_platform_metrics_region ON platform_metrics(region)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_platform_metrics_city ON platform_metrics(city)")
            logger.info("✓ Added region columns to platform_metrics table")
        else:
            logger.info("✓ Region columns already exist in platform_metrics table")
        
        # Commit changes
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

def verify_migration():
    """Verify that the migration was successful."""
    db_path = Path("ad-platform.db")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check events table
        cursor.execute("PRAGMA table_info(events)")
        events_columns = [column[1] for column in cursor.fetchall()]
        
        # Check web3_events table
        cursor.execute("PRAGMA table_info(web3_events)")
        web3_events_columns = [column[1] for column in cursor.fetchall()]
        
        # Check platform_metrics table
        cursor.execute("PRAGMA table_info(platform_metrics)")
        platform_metrics_columns = [column[1] for column in cursor.fetchall()]
        
        required_columns = ['country', 'region', 'city']
        
        logger.info("\n=== Migration Verification ===")
        logger.info(f"Events table columns: {events_columns}")
        logger.info(f"Web3 Events table columns: {web3_events_columns}")
        logger.info(f"Platform Metrics table columns: {platform_metrics_columns}")
        
        all_good = True
        for table_name, columns in [
            ("events", events_columns),
            ("web3_events", web3_events_columns),
            ("platform_metrics", platform_metrics_columns)
        ]:
            missing = [col for col in required_columns if col not in columns]
            if missing:
                logger.error(f"❌ {table_name} table missing columns: {missing}")
                all_good = False
            else:
                logger.info(f"✅ {table_name} table has all required columns")
        
        if all_good:
            logger.info("✅ All tables have the required region tracking columns!")
        else:
            logger.error("❌ Some tables are missing required columns!")
        
        return all_good
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return False
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    logger.info("Starting region tracking migration...")
    
    if migrate_database():
        logger.info("Migration completed. Verifying...")
        verify_migration()
    else:
        logger.error("Migration failed!")
        exit(1)
