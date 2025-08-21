#!/usr/bin/env python3
"""
Complete UUID Migration - Convert original integer ID columns to UUID type.
This script finishes the UUID migration by updating the actual column types.
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

def complete_uuid_migration():
    """Complete the UUID migration by converting ID columns."""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        logger.info("🚀 COMPLETING UUID MIGRATION")
        logger.info("=" * 50)
        
        # List of tables to migrate (in dependency order)
        tables_to_migrate = [
            'platform_users',      # No dependencies
            'client_companies',    # Depends on platform_users
            'client_app_users',    # No dependencies
            'events',              # Depends on client_companies
            'web3_events',        # Depends on client_companies
            'platform_metrics'     # Depends on client_companies
        ]
        
        # Step 1: Drop primary key constraints
        logger.info("📋 STEP 1: Dropping primary key constraints...")
        for table_name in tables_to_migrate:
            try:
                cursor.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {table_name}_pkey")
                logger.info(f"✅ Dropped primary key constraint from {table_name}")
            except Exception as e:
                logger.warning(f"⚠️  Could not drop primary key from {table_name}: {e}")
        
        conn.commit()
        
        # Step 2: Drop old integer ID columns and rename UUID columns
        logger.info("\n📋 STEP 2: Converting ID columns to UUID...")
        for table_name in tables_to_migrate:
            try:
                # Drop the old integer ID column
                cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS id")
                logger.info(f"✅ Dropped old integer ID column from {table_name}")
                
                # Rename id_uuid to id
                cursor.execute(f"ALTER TABLE {table_name} RENAME COLUMN id_uuid TO id")
                logger.info(f"✅ Renamed id_uuid to id in {table_name}")
                
                # Make the new ID column NOT NULL
                cursor.execute(f"ALTER TABLE {table_name} ALTER COLUMN id SET NOT NULL")
                logger.info(f"✅ Made ID column NOT NULL in {table_name}")
                
            except Exception as e:
                logger.error(f"❌ Failed to convert ID column in {table_name}: {e}")
                return False
        
        # Step 3: Convert foreign key columns
        logger.info("\n📋 STEP 3: Converting foreign key columns...")
        
        # Convert client_companies.platform_user_id
        try:
            cursor.execute("ALTER TABLE client_companies DROP COLUMN IF EXISTS platform_user_id")
            cursor.execute("ALTER TABLE client_companies RENAME COLUMN platform_user_id_uuid TO platform_user_id")
            cursor.execute("ALTER TABLE client_companies ALTER COLUMN platform_user_id SET NOT NULL")
            logger.info("✅ Converted client_companies.platform_user_id to UUID")
        except Exception as e:
            logger.error(f"❌ Failed to convert client_companies.platform_user_id: {e}")
        
        # Convert events.client_company_id
        try:
            cursor.execute("ALTER TABLE events DROP COLUMN IF EXISTS client_company_id")
            cursor.execute("ALTER TABLE events RENAME COLUMN client_company_id_uuid TO client_company_id")
            cursor.execute("ALTER TABLE events ALTER COLUMN client_company_id SET NOT NULL")
            logger.info("✅ Converted events.client_company_id to UUID")
        except Exception as e:
            logger.error(f"❌ Failed to convert events.client_company_id: {e}")
        
        # Convert web3_events.client_company_id
        try:
            cursor.execute("ALTER TABLE web3_events DROP COLUMN IF EXISTS client_company_id")
            cursor.execute("ALTER TABLE web3_events RENAME COLUMN client_company_id_uuid TO client_company_id")
            cursor.execute("ALTER TABLE web3_events ALTER COLUMN client_company_id SET NOT NULL")
            logger.info("✅ Converted web3_events.client_company_id to UUID")
        except Exception as e:
            logger.error(f"❌ Failed to convert web3_events.client_company_id: {e}")
        
        # Convert platform_metrics.client_company_id
        try:
            cursor.execute("ALTER TABLE platform_metrics DROP COLUMN IF EXISTS client_company_id")
            cursor.execute("ALTER TABLE platform_metrics RENAME COLUMN client_company_id_uuid TO client_company_id")
            cursor.execute("ALTER TABLE platform_metrics ALTER COLUMN client_company_id SET NOT NULL")
            logger.info("✅ Converted platform_metrics.client_company_id to UUID")
        except Exception as e:
            logger.error(f"❌ Failed to convert platform_metrics.client_company_id: {e}")
        
        # Step 4: Recreate primary key constraints
        logger.info("\n📋 STEP 4: Recreating primary key constraints...")
        for table_name in tables_to_migrate:
            try:
                cursor.execute(f"ALTER TABLE {table_name} ADD PRIMARY KEY (id)")
                logger.info(f"✅ Added primary key constraint to {table_name}")
            except Exception as e:
                logger.error(f"❌ Failed to add primary key to {table_name}: {e}")
        
        # Step 5: Recreate foreign key constraints
        logger.info("\n📋 STEP 5: Recreating foreign key constraints...")
        
        # client_companies -> platform_users
        try:
            cursor.execute("""
                ALTER TABLE client_companies 
                ADD CONSTRAINT client_companies_platform_user_id_fkey 
                FOREIGN KEY (platform_user_id) REFERENCES platform_users(id)
            """)
            logger.info("✅ Added foreign key constraint: client_companies -> platform_users")
        except Exception as e:
            logger.error(f"❌ Failed to add foreign key constraint: {e}")
        
        # events -> client_companies
        try:
            cursor.execute("""
                ALTER TABLE events 
                ADD CONSTRAINT events_client_company_id_fkey 
                FOREIGN KEY (client_company_id) REFERENCES client_companies(id)
            """)
            logger.info("✅ Added foreign key constraint: events -> client_companies")
        except Exception as e:
            logger.error(f"❌ Failed to add foreign key constraint: {e}")
        
        # web3_events -> client_companies
        try:
            cursor.execute("""
                ALTER TABLE web3_events 
                ADD CONSTRAINT web3_events_client_company_id_fkey 
                FOREIGN KEY (client_company_id) REFERENCES client_companies(id)
            """)
            logger.info("✅ Added foreign key constraint: web3_events -> client_companies")
        except Exception as e:
            logger.error(f"❌ Failed to add foreign key constraint: {e}")
        
        # platform_metrics -> client_companies
        try:
            cursor.execute("""
                ALTER TABLE platform_metrics 
                ADD CONSTRAINT platform_metrics_client_company_id_fkey 
                FOREIGN KEY (client_company_id) REFERENCES client_companies(id)
            """)
            logger.info("✅ Added foreign key constraint: platform_metrics -> client_companies")
        except Exception as e:
            logger.error(f"❌ Failed to add foreign key constraint: {e}")
        
        conn.commit()
        logger.info("\n🎉 UUID MIGRATION COMPLETED SUCCESSFULLY!")
        logger.info("=" * 50)
        logger.info("✅ All ID columns are now UUID type")
        logger.info("✅ All foreign key relationships restored")
        logger.info("✅ Primary key constraints recreated")
        logger.info("✅ Your database is now fully UUID-based!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    logger.info("Starting UUID migration completion...")
    if complete_uuid_migration():
        logger.info("✅ UUID migration completion successful!")
    else:
        logger.error("❌ UUID migration completion failed!")
        exit(1)
