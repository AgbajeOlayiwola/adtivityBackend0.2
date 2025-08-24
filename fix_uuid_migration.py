#!/usr/bin/env python3
"""
Fix incomplete UUID migration by adding missing foreign key UUID columns.
Run this after the main UUID migration to complete the process.
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

def fix_uuid_migration():
    """Fix the incomplete UUID migration."""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        logger.info("🔧 FIXING INCOMPLETE UUID MIGRATION")
        logger.info("=" * 50)
        
        # Step 1: Add missing foreign key UUID columns
        logger.info("📋 STEP 1: Adding missing foreign key UUID columns...")
        
        # Add platform_user_id_uuid to client_companies
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'client_companies' AND column_name = 'platform_user_id_uuid'
        """)
        
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE client_companies ADD COLUMN platform_user_id_uuid UUID")
            logger.info("✅ Added platform_user_id_uuid to client_companies")
        else:
            logger.info("✅ platform_user_id_uuid already exists in client_companies")
        
        # Add client_company_id_uuid to events
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'events' AND column_name = 'client_company_id_uuid'
        """)
        
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE events ADD COLUMN client_company_id_uuid UUID")
            logger.info("✅ Added client_company_id_uuid to events")
        else:
            logger.info("✅ client_company_id_uuid already exists in events")
        
        # Add client_company_id_uuid to web3_events
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'web3_events' AND column_name = 'client_company_id_uuid'
        """)
        
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE web3_events ADD COLUMN client_company_id_uuid UUID")
            logger.info("✅ Added client_company_id_uuid to web3_events")
        else:
            logger.info("✅ client_company_id_uuid already exists in web3_events")
        
        # Add client_company_id_uuid to platform_metrics
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'platform_metrics' AND column_name = 'client_company_id_uuid'
        """)
        
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE platform_metrics ADD COLUMN client_company_id_uuid UUID")
            logger.info("✅ Added client_company_id_uuid to platform_metrics")
        else:
            logger.info("✅ client_company_id_uuid already exists in platform_metrics")
        
        conn.commit()
        logger.info("✅ Foreign key UUID columns added successfully")
        
        # Step 2: Update foreign key references
        logger.info("\n📋 STEP 2: Updating foreign key references...")
        
        # Update client_companies.platform_user_id
        try:
            cursor.execute("""
                UPDATE client_companies 
                SET platform_user_id_uuid = platform_users.id_uuid 
                FROM platform_users 
                WHERE client_companies.platform_user_id = platform_users.id
            """)
            logger.info("✅ Updated client_companies.platform_user_id references")
        except Exception as e:
            logger.error(f"❌ Failed to update client_companies references: {e}")
        
        # Update events.client_company_id
        try:
            cursor.execute("""
                UPDATE events 
                SET client_company_id_uuid = client_companies.id_uuid 
                FROM client_companies 
                WHERE events.client_company_id = client_companies.id
            """)
            logger.info("✅ Updated events.client_company_id references")
        except Exception as e:
            logger.error(f"❌ Failed to update events references: {e}")
        
        # Update web3_events.client_company_id
        try:
            cursor.execute("""
                UPDATE web3_events 
                SET client_company_id_uuid = client_companies.id_uuid 
                FROM client_companies 
                WHERE web3_events.client_company_id = client_companies.id
            """)
            logger.info("✅ Updated web3_events.client_company_id references")
    except Exception as e:
            logger.error(f"❌ Failed to update web3_events references: {e}")
        
        # Update platform_metrics.client_company_id
        try:
            cursor.execute("""
                UPDATE platform_metrics 
                SET client_company_id_uuid = client_companies.id_uuid 
                FROM client_companies 
                WHERE platform_metrics.client_company_id = client_companies.id
            """)
            logger.info("✅ Updated platform_metrics.client_company_id references")
        except Exception as e:
            logger.error(f"❌ Failed to update platform_metrics references: {e}")
        
        conn.commit()
        logger.info("\n🎉 UUID MIGRATION FIX COMPLETED SUCCESSFULLY!")
        logger.info("=" * 50)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Fix failed: {e}")
        if conn:
        conn.rollback()
        return False
    finally:
        if conn:
        conn.close()

if __name__ == "__main__":
    logger.info("Starting UUID migration fix...")
    if fix_uuid_migration():
        logger.info("✅ UUID migration fix completed successfully!")
    else:
        logger.error("❌ UUID migration fix failed!")
        exit(1)
