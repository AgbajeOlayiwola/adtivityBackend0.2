#!/usr/bin/env python3
"""
Drop all constraints to allow UUID migration.
"""

import os
import psycopg2
import logging
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL not set")
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
        logger.error(f"Connection failed: {e}")
        return None

def drop_all_constraints():
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        logger.info("🗑️  DROPPING ALL CONSTRAINTS")
        logger.info("=" * 40)
        
        # Find all foreign key constraints
        cursor.execute("""
            SELECT tc.table_name, tc.constraint_name
            FROM information_schema.table_constraints tc
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
        """)
        
        fks = cursor.fetchall()
        logger.info(f"Found {len(fks)} foreign key constraints")
        
        # Drop all foreign keys
        for table_name, constraint_name in fks:
            try:
                cursor.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name}")
                logger.info(f"✅ Dropped FK: {constraint_name}")
            except Exception as e:
                logger.warning(f"⚠️  Could not drop {constraint_name}: {e}")
        
        # Find all primary key constraints
        cursor.execute("""
            SELECT tc.table_name, tc.constraint_name
            FROM information_schema.table_constraints tc
            WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_schema = 'public'
        """)
        
        pks = cursor.fetchall()
        logger.info(f"Found {len(pks)} primary key constraints")
        
        # Drop all primary keys
        for table_name, constraint_name in pks:
            try:
                cursor.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name}")
                logger.info(f"✅ Dropped PK: {constraint_name}")
            except Exception as e:
                logger.warning(f"⚠️  Could not drop {constraint_name}: {e}")
        
        conn.commit()
        logger.info("✅ All constraints dropped successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if drop_all_constraints():
        logger.info("✅ Ready for UUID migration!")
    else:
        logger.error("❌ Failed to drop constraints!")
        exit(1)
