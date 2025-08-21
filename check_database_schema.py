#!/usr/bin/env python3
"""
Database Schema Inspector - Check current table structure before migration.
Run this first to understand your current database state.
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
        return conn
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        return None

def inspect_database_schema():
    """Inspect the current database schema."""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        logger.info("🔍 INSPECTING DATABASE SCHEMA")
        logger.info("=" * 50)
        
        # Get list of all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        logger.info(f"📋 Found {len(tables)} tables: {tables}")
        logger.info("")
        
        # Inspect each table's structure
        for table_name in tables:
            logger.info(f"📊 TABLE: {table_name}")
            logger.info("-" * 30)
            
            # Get column information
            cursor.execute("""
                SELECT 
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable,
                    column_default
                FROM information_schema.columns 
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position
            """, (table_name,))
            
            columns = cursor.fetchall()
            
            for col in columns:
                col_name, data_type, max_length, nullable, default_val = col
                length_info = f"({max_length})" if max_length else ""
                nullable_info = "NULL" if nullable == "YES" else "NOT NULL"
                default_info = f" DEFAULT {default_val}" if default_val else ""
                
                logger.info(f"  {col_name:<20} {data_type}{length_info:<15} {nullable_info:<10}{default_info}")
            
            # Get index information
            cursor.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes 
                WHERE tablename = %s
                ORDER BY indexname
            """, (table_name,))
            
            indexes = cursor.fetchall()
            if indexes:
                logger.info("  📍 Indexes:")
                for idx_name, idx_def in indexes:
                    logger.info(f"    {idx_name}: {idx_def}")
            
            # Get row count
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                logger.info(f"  📈 Row count: {row_count:,}")
            except Exception as e:
                logger.info(f"  📈 Row count: Unable to count - {e}")
            
            logger.info("")
        
        # Check for specific region-related columns
        logger.info("🎯 REGION TRACKING STATUS")
        logger.info("=" * 50)
        
        region_columns = ['country', 'region', 'city', 'ip_address']
        target_tables = ['events', 'web3_events', 'platform_metrics']
        
        for table_name in target_tables:
            if table_name in tables:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND table_schema = 'public'
                """, (table_name,))
                
                existing_columns = [col[0] for col in cursor.fetchall()]
                missing_columns = [col for col in region_columns if col not in existing_columns]
                
                if missing_columns:
                    logger.info(f"❌ {table_name}: Missing columns: {missing_columns}")
                else:
                    logger.info(f"✅ {table_name}: All region columns present")
            else:
                logger.info(f"⚠️  {table_name}: Table does not exist")
        
        logger.info("")
        logger.info("🔧 MIGRATION RECOMMENDATIONS")
        logger.info("=" * 50)
        
        # Provide migration recommendations
        for table_name in target_tables:
            if table_name in tables:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND table_schema = 'public'
                """, (table_name,))
                
                existing_columns = [col[0] for col in cursor.fetchall()]
                missing_columns = [col for col in region_columns if col not in existing_columns]
                
                if missing_columns:
                    logger.info(f"📝 {table_name}: Need to add columns: {missing_columns}")
                else:
                    logger.info(f"✅ {table_name}: No migration needed")
        
        return True
        
    except Exception as e:
        logger.error(f"Inspection failed: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    logger.info("Starting database schema inspection...")
    if inspect_database_schema():
        logger.info("✅ Schema inspection completed successfully!")
    else:
        logger.error("❌ Schema inspection failed!")
        exit(1)
