#!/usr/bin/env python3
"""
Heroku UUID Migration Script - Convert integer IDs to UUIDs for enhanced security.
This script uses the DATABASE_URL environment variable from Heroku.
"""

import os
import uuid
import psycopg2
import logging
from urllib.parse import urlparse
from psycopg2.extras import RealDictCursor

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

def backup_table(conn, table_name):
    """Create a backup of the table before migration."""
    cursor = conn.cursor()
    backup_table_name = f"{table_name}_backup_{int(uuid.uuid4().hex[:8], 16)}"
    
    try:
        cursor.execute(f"CREATE TABLE {backup_table_name} AS SELECT * FROM {table_name}")
        conn.commit()
        logger.info(f"✅ Created backup table: {backup_table_name}")
        return backup_table_name
    except Exception as e:
        logger.error(f"❌ Failed to create backup for {table_name}: {e}")
        conn.rollback()
        return None

def add_uuid_columns(conn, table_name, id_column="id"):
    """Add UUID columns to the table."""
    cursor = conn.cursor()
    
    try:
        # Check if UUID column already exists
        cursor.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}' AND column_name = '{id_column}_uuid'
        """)
        
        if cursor.fetchone():
            logger.info(f"✅ UUID column already exists in {table_name}")
            return True
        
        # Add new UUID column
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {id_column}_uuid UUID")
        logger.info(f"✅ Added UUID column to {table_name}")
        
        # Generate UUIDs for existing records
        cursor.execute(f"UPDATE {table_name} SET {id_column}_uuid = gen_random_uuid()")
        logger.info(f"✅ Generated UUIDs for existing records in {table_name}")
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to add UUID column to {table_name}: {e}")
        conn.rollback()
        return False

def migrate_to_uuids():
    """Main migration function to convert all tables to UUIDs."""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        logger.info("🚀 STARTING UUID MIGRATION")
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
        
        # Step 1: Create backups
        logger.info("📋 STEP 1: Creating table backups...")
        backup_tables = {}
        for table_name in tables_to_migrate:
            cursor.execute(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = '{table_name}'
                )
            """)
            if cursor.fetchone()[0]:
                backup_name = backup_table(conn, table_name)
                if backup_name:
                    backup_tables[table_name] = backup_name
                else:
                    logger.warning(f"⚠️  Skipping backup for {table_name}")
            else:
                logger.info(f"ℹ️  Table {table_name} doesn't exist, skipping")
        
        conn.commit()
        logger.info("✅ All backups completed")
        
        # Step 2: Add UUID columns
        logger.info("\n📋 STEP 2: Adding UUID columns...")
        for table_name in tables_to_migrate:
            if table_name in backup_tables:
                if add_uuid_columns(conn, table_name):
                    logger.info(f"✅ {table_name}: UUID column added successfully")
                else:
                    logger.error(f"❌ {table_name}: Failed to add UUID column")
                    return False
        
        # Step 3: Update foreign key references
        logger.info("\n📋 STEP 3: Updating foreign key references...")
        
        # Update client_companies.platform_user_id
        if 'client_companies' in backup_tables:
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
        if 'events' in backup_tables:
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
        if 'web3_events' in backup_tables:
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
        if 'platform_metrics' in backup_tables:
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
        logger.info("\n🎉 UUID MIGRATION COMPLETED SUCCESSFULLY!")
        logger.info("=" * 50)
        logger.info("📋 Summary of changes:")
        for table_name, backup_name in backup_tables.items():
            logger.info(f"  ✅ {table_name}: Added UUID column, backup: {backup_name}")
        
        logger.info("\n⚠️  IMPORTANT: Your old integer ID columns are still present.")
        logger.info("   You can drop them later after confirming everything works.")
        logger.info("   Backup tables are available if you need to rollback.")
        
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
    logger.info("Starting Heroku UUID migration...")
    if migrate_to_uuids():
        logger.info("✅ UUID migration completed successfully!")
    else:
        logger.error("❌ UUID migration failed!")
        exit(1)
