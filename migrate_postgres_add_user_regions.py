#!/usr/bin/env python3
"""
PostgreSQL migration script to add region and city columns to client_app_users table.
This script is designed to work with Heroku/PostgreSQL databases.
"""

import os
import psycopg2
import logging
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_connection():
    """Get database connection from DATABASE_URL environment variable."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL environment variable not found")
        return None
    
    try:
        # Parse the DATABASE_URL
        parsed = urlparse(database_url)
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password
        )
        
        logger.info("✅ Connected to PostgreSQL database successfully")
        return conn
        
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        return None

def check_table_schema(conn):
    """Check the current schema of client_app_users table."""
    try:
        cursor = conn.cursor()
        
        # Get table information
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'client_app_users'
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        
        logger.info("📋 Current client_app_users table schema:")
        logger.info("=" * 60)
        
        existing_columns = []
        for col in columns:
            column_name, data_type, is_nullable = col
            existing_columns.append(column_name)
            logger.info(f"  {column_name}: {data_type} ({'NULL' if is_nullable == 'YES' else 'NOT NULL'})")
        
        logger.info("=" * 60)
        
        return existing_columns
        
    except Exception as e:
        logger.error(f"❌ Failed to check table schema: {e}")
        return []

def add_missing_columns(conn, existing_columns):
    """Add missing region and city columns if they don't exist."""
    try:
        cursor = conn.cursor()
        
        # Check and add region column
        if 'region' not in existing_columns:
            logger.info("🔧 Adding region column...")
            cursor.execute("""
                ALTER TABLE client_app_users 
                ADD COLUMN region VARCHAR(100)
            """)
            logger.info("✅ Added region column")
        else:
            logger.info("ℹ️  region column already exists")
        
        # Check and add city column
        if 'city' not in existing_columns:
            logger.info("🔧 Adding city column...")
            cursor.execute("""
                ALTER TABLE client_app_users 
                ADD COLUMN city VARCHAR(100)
            """)
            logger.info("✅ Added city column")
        else:
            logger.info("ℹ️  city column already exists")
        
        # Check and add company_id column
        if 'company_id' not in existing_columns:
            logger.info("🔧 Adding company_id column...")
            cursor.execute("""
                ALTER TABLE client_app_users 
                ADD COLUMN company_id UUID
            """)
            logger.info("✅ Added company_id column")
        else:
            logger.info("ℹ️  company_id column already exists")
        
        # Check and add platform_user_id column
        if 'platform_user_id' not in existing_columns:
            logger.info("🔧 Adding platform_user_id column...")
            cursor.execute("""
                ALTER TABLE client_app_users 
                ADD COLUMN platform_user_id UUID
            """)
            logger.info("✅ Added platform_user_id column")
        else:
            logger.info("ℹ️  platform_user_id column already exists")
        
        # Check and add user_id column
        if 'user_id' not in existing_columns:
            logger.info("🔧 Adding user_id column...")
            cursor.execute("""
                ALTER TABLE client_app_users 
                ADD COLUMN user_id VARCHAR
            """)
            logger.info("✅ Added user_id column")
        else:
            logger.info("ℹ️  user_id column already exists")
        
        # Commit the changes
        conn.commit()
        logger.info("✅ All column additions committed successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to add columns: {e}")
        conn.rollback()
        return False

def add_foreign_key_constraints(conn):
    """Add foreign key constraints if they don't exist."""
    try:
        cursor = conn.cursor()
        
        logger.info("🔧 Adding foreign key constraints...")
        
        # Add foreign key for company_id
        try:
            cursor.execute("""
                ALTER TABLE client_app_users 
                ADD CONSTRAINT fk_client_app_users_company 
                FOREIGN KEY (company_id) REFERENCES client_companies(id)
            """)
            logger.info("✅ Added company_id foreign key constraint")
        except Exception as e:
            if "already exists" in str(e):
                logger.info("ℹ️  company_id foreign key constraint already exists")
            else:
                logger.warning(f"⚠️  Could not add company_id foreign key: {e}")
        
        # Add foreign key for platform_user_id
        try:
            cursor.execute("""
                ALTER TABLE client_app_users 
                ADD CONSTRAINT fk_client_app_users_platform_user 
                FOREIGN KEY (platform_user_id) REFERENCES platform_users(id)
            """)
            logger.info("✅ Added platform_user_id foreign key constraint")
        except Exception as e:
            if "already exists" in str(e):
                logger.info("ℹ️  platform_user_id foreign key constraint already exists")
            else:
                logger.warning(f"⚠️  Could not add platform_user_id foreign key: {e}")
        
        # Commit the changes
        conn.commit()
        logger.info("✅ Foreign key constraints added successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to add foreign key constraints: {e}")
        conn.rollback()
        return False

def verify_migration(conn):
    """Verify that all required columns are present."""
    try:
        cursor = conn.cursor()
        
        # Check final schema
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'client_app_users'
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        
        required_columns = ['region', 'city', 'company_id', 'platform_user_id', 'user_id']
        existing_columns = [col[0] for col in columns]
        
        logger.info("\n🔍 Verifying migration...")
        logger.info("=" * 60)
        
        all_present = True
        for required_col in required_columns:
            if required_col in existing_columns:
                logger.info(f"✅ {required_col}: Present")
            else:
                logger.info(f"❌ {required_col}: Missing")
                all_present = False
        
        logger.info("=" * 60)
        
        if all_present:
            logger.info("🎉 All required columns are present!")
        else:
            logger.error("❌ Some required columns are missing")
        
        return all_present
        
    except Exception as e:
        logger.error(f"❌ Failed to verify migration: {e}")
        return False

def main():
    """Main migration function."""
    logger.info("🚀 Starting PostgreSQL client_app_users migration...")
    logger.info("=" * 60)
    
    # Get database connection
    conn = get_database_connection()
    if not conn:
        return False
    
    try:
        # Check current schema
        existing_columns = check_table_schema(conn)
        if not existing_columns:
            return False
        
        # Add missing columns
        if not add_missing_columns(conn, existing_columns):
            return False
        
        # Add foreign key constraints
        if not add_foreign_key_constraints(conn):
            return False
        
        # Verify migration
        if not verify_migration(conn):
            return False
        
        logger.info("\n🎉 Migration completed successfully!")
        logger.info("📋 The CSV import should now work correctly")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False
        
    finally:
        if conn:
            conn.close()
            logger.info("🔌 Database connection closed")

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)
