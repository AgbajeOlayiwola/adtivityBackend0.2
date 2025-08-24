#!/usr/bin/env python3
"""
Script to inspect the current PostgreSQL database schema.
This will show us exactly what columns exist in the client_app_users table.
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
        logger.info("💡 Set it with: export DATABASE_URL='your_heroku_postgresql_url'")
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

def check_table_exists(conn, table_name):
    """Check if a table exists in the database."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            );
        """, (table_name,))
        
        exists = cursor.fetchone()[0]
        return exists
        
    except Exception as e:
        logger.error(f"❌ Failed to check if table {table_name} exists: {e}")
        return False

def get_table_schema(conn, table_name):
    """Get detailed schema information for a specific table."""
    try:
        cursor = conn.cursor()
        
        # Get column information
        cursor.execute("""
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length,
                numeric_precision,
                numeric_scale
            FROM information_schema.columns 
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        
        columns = cursor.fetchall()
        
        # Get index information
        cursor.execute("""
            SELECT 
                indexname,
                indexdef
            FROM pg_indexes 
            WHERE tablename = %s
        """, (table_name,))
        
        indexes = cursor.fetchall()
        
        # Get constraint information
        cursor.execute("""
            SELECT 
                conname,
                contype,
                pg_get_constraintdef(oid) as definition
            FROM pg_constraint 
            WHERE conrelid = %s::regclass
        """, (table_name,))
        
        constraints = cursor.fetchall()
        
        return columns, indexes, constraints
        
    except Exception as e:
        logger.error(f"❌ Failed to get schema for table {table_name}: {e}")
        return [], [], []

def display_table_schema(table_name, columns, indexes, constraints):
    """Display the table schema in a formatted way."""
    logger.info(f"\n📊 TABLE: {table_name}")
    logger.info("=" * 60)
    
    if not columns:
        logger.info("❌ No columns found or table doesn't exist")
        return
    
    # Display columns
    logger.info("📋 COLUMNS:")
    logger.info("-" * 40)
    
    for col in columns:
        column_name, data_type, is_nullable, column_default, char_max_length, num_precision, num_scale = col
        
        # Format the data type display
        if char_max_length:
            type_display = f"{data_type}({char_max_length})"
        elif num_precision and num_scale:
            type_display = f"{data_type}({num_precision},{num_scale})"
        elif num_precision:
            type_display = f"{data_type}({num_precision})"
        else:
            type_display = data_type
        
        nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
        default = f" DEFAULT {column_default}" if column_default else ""
        
        logger.info(f"  {column_name}: {type_display} {nullable}{default}")
    
    # Display indexes
    if indexes:
        logger.info("\n🔍 INDEXES:")
        logger.info("-" * 40)
        for idx in indexes:
            index_name, index_def = idx
            logger.info(f"  {index_name}: {index_def}")
    
    # Display constraints
    if constraints:
        logger.info("\n🔒 CONSTRAINTS:")
        logger.info("-" * 40)
        for con in constraints:
            con_name, con_type, con_def = con
            con_type_display = {
                'p': 'PRIMARY KEY',
                'f': 'FOREIGN KEY',
                'u': 'UNIQUE',
                'c': 'CHECK'
            }.get(con_type, con_type.upper())
            
            logger.info(f"  {con_name} ({con_type_display}): {con_def}")
    
    logger.info("=" * 60)

def check_specific_columns(conn, table_name, required_columns):
    """Check if specific required columns exist in the table."""
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s
        """, (table_name,))
        
        existing_columns = [col[0] for col in cursor.fetchall()]
        
        logger.info(f"\n🎯 CHECKING REQUIRED COLUMNS FOR {table_name}:")
        logger.info("=" * 60)
        
        missing_columns = []
        for required_col in required_columns:
            if required_col in existing_columns:
                logger.info(f"✅ {required_col}: Present")
            else:
                logger.info(f"❌ {required_col}: Missing")
                missing_columns.append(required_col)
        
        if missing_columns:
            logger.info(f"\n⚠️  MISSING COLUMNS: {', '.join(missing_columns)}")
            logger.info("💡 These need to be added for CSV import to work")
        else:
            logger.info(f"\n🎉 All required columns are present!")
        
        logger.info("=" * 60)
        
        return missing_columns
        
    except Exception as e:
        logger.error(f"❌ Failed to check required columns: {e}")
        return required_columns

def get_table_row_count(conn, table_name):
    """Get the row count for a table."""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        return count
    except Exception as e:
        logger.error(f"❌ Failed to get row count for {table_name}: {e}")
        return 0

def main():
    """Main function to inspect the database schema."""
    logger.info("🔍 POSTGRESQL DATABASE SCHEMA INSPECTION")
    logger.info("=" * 60)
    
    # Get database connection
    conn = get_database_connection()
    if not conn:
        return
    
    try:
        # Check if client_app_users table exists
        if not check_table_exists(conn, 'client_app_users'):
            logger.error("❌ Table 'client_app_users' does not exist!")
            logger.info("💡 This suggests the database schema is incomplete")
            return
        
        # Get detailed schema for client_app_users
        columns, indexes, constraints = get_table_schema(conn, 'client_app_users')
        display_table_schema('client_app_users', columns, indexes, constraints)
        
        # Check row count
        row_count = get_table_row_count(conn, 'client_app_users')
        logger.info(f"📊 Row count: {row_count}")
        
        # Check for required columns for CSV import
        required_columns = ['region', 'city', 'company_id', 'platform_user_id', 'user_id']
        missing_columns = check_specific_columns(conn, 'client_app_users', required_columns)
        
        # Summary and recommendations
        logger.info("\n📋 SUMMARY & RECOMMENDATIONS:")
        logger.info("=" * 60)
        
        if missing_columns:
            logger.info("🔧 ACTION REQUIRED:")
            logger.info(f"   Run migration to add missing columns: {', '.join(missing_columns)}")
            logger.info("   Use: python migrate_postgres_add_user_regions.py")
        else:
            logger.info("✅ NO ACTION REQUIRED:")
            logger.info("   All required columns are present")
            logger.info("   CSV import should work correctly")
        
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Schema inspection failed: {e}")
        
    finally:
        if conn:
            conn.close()
            logger.info("🔌 Database connection closed")

if __name__ == "__main__":
    main()
