#!/usr/bin/env python3
"""
Fix script for the failed UUID migration.
This script will properly handle foreign key constraints and complete the migration.
"""

import os
import sys
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor

# Set the database URL for PostgreSQL
os.environ['DATABASE_URL'] = 'postgresql://adtivity:adtivity123@localhost:5432/adtivity'

def connect_to_database():
    """Connect to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port="5432",
            database="adtivity",
            user="adtivity",
            password="adtivity123"
        )
        return conn
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        sys.exit(1)

def check_table_state(conn, table_name):
    """Check the current state of a table."""
    cursor = conn.cursor()
    try:
        cursor.execute(f"""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        
        print(f"\nTable {table_name} current state:")
        for col in columns:
            print(f"  {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")
        
        return columns
    except Exception as e:
        print(f"Failed to check table state for {table_name}: {e}")
        return None

def check_foreign_keys(conn, table_name):
    """Check foreign key constraints for a table."""
    cursor = conn.cursor()
    try:
        cursor.execute(f"""
            SELECT 
                tc.constraint_name,
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY' 
            AND tc.table_name = '{table_name}'
        """)
        fks = cursor.fetchall()
        
        if fks:
            print(f"\nForeign keys for {table_name}:")
            for fk in fks:
                print(f"  {fk[0]}: {fk[1]}.{fk[2]} -> {fk[3]}.{fk[4]}")
        
        return fks
    except Exception as e:
        print(f"Failed to check foreign keys for {table_name}: {e}")
        return None

def cleanup_failed_migration(conn, table_name):
    """Clean up any failed migration artifacts."""
    cursor = conn.cursor()
    try:
        # Check if there's a UUID column that was partially created
        cursor.execute(f"""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = '{table_name}' AND column_name LIKE '%_uuid'
        """)
        uuid_columns = cursor.fetchall()
        
        for col in uuid_columns:
            col_name = col[0]
            print(f"Removing partial UUID column: {col_name}")
            cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS {col_name}")
        
        conn.commit()
        print(f"Cleaned up failed migration artifacts for {table_name}")
        return True
    except Exception as e:
        print(f"Failed to cleanup {table_name}: {e}")
        conn.rollback()
        return False

def migrate_table_with_foreign_keys(conn, table_name, foreign_keys=None):
    """Migrate a table to UUIDs, properly handling foreign keys."""
    print(f"\nMigrating table: {table_name}")
    
    cursor = conn.cursor()
    
    try:
        # Step 1: Add UUID column
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN id_uuid UUID")
        print(f"Added UUID column to {table_name}")
        
        # Step 2: Generate UUIDs for existing records
        cursor.execute(f"UPDATE {table_name} SET id_uuid = gen_random_uuid()")
        print(f"Generated UUIDs for existing records in {table_name}")
        
        # Step 3: Update foreign key columns in dependent tables
        if foreign_keys:
            for fk_column, ref_table in foreign_keys.items():
                print(f"Updating foreign key {fk_column} in {table_name}")
                
                # Add UUID column for foreign key
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {fk_column}_uuid UUID")
                
                # Update foreign key references
                cursor.execute(f"""
                    UPDATE {table_name} 
                    SET {fk_column}_uuid = ref.id_uuid
                    FROM {ref_table} ref
                    WHERE {table_name}.{fk_column} = ref.id
                """)
                
                # Drop old foreign key constraint
                cursor.execute(f"""
                    SELECT constraint_name 
                    FROM information_schema.table_constraints 
                    WHERE table_name = '{table_name}' 
                    AND constraint_type = 'FOREIGN KEY'
                    AND constraint_name LIKE '%{fk_column}%'
                """)
                constraint_result = cursor.fetchone()
                if constraint_result:
                    constraint_name = constraint_result[0]
                    cursor.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name}")
                    print(f"Dropped foreign key constraint: {constraint_name}")
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Failed to migrate {table_name}: {e}")
        conn.rollback()
        return False

def finalize_migration(conn, table_name, foreign_keys=None):
    """Finalize the migration by swapping columns and recreating constraints."""
    cursor = conn.cursor()
    
    try:
        # Step 1: Drop old integer columns
        if foreign_keys:
            for fk_column, ref_table in foreign_keys.items():
                cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN {fk_column}")
                cursor.execute(f"ALTER TABLE {table_name} RENAME COLUMN {fk_column}_uuid TO {fk_column}")
                print(f"Swapped foreign key column {fk_column} in {table_name}")
        
        # Step 2: Drop old primary key and swap ID column
        cursor.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {table_name}_pkey")
        cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN id")
        cursor.execute(f"ALTER TABLE {table_name} RENAME COLUMN id_uuid TO id")
        cursor.execute(f"ALTER TABLE {table_name} ADD PRIMARY KEY (id)")
        print(f"Swapped primary key column in {table_name}")
        
        # Step 3: Recreate foreign key constraints
        if foreign_keys:
            for fk_column, ref_table in foreign_keys.items():
                cursor.execute(f"""
                    ALTER TABLE {table_name} 
                    ADD CONSTRAINT {table_name}_{fk_column}_fkey 
                    FOREIGN KEY ({fk_column}) 
                    REFERENCES {ref_table}(id)
                """)
                print(f"Recreated foreign key constraint for {fk_column} in {table_name}")
        
        conn.commit()
        print(f"Finalized migration for {table_name}")
        return True
        
    except Exception as e:
        print(f"Failed to finalize migration for {table_name}: {e}")
        conn.rollback()
        return False

def main():
    """Main fix function."""
    print("Fixing Failed UUID Migration")
    print("=" * 50)
    
    # Connect to database
    conn = connect_to_database()
    print("Connected to database successfully")
    
    try:
        # Check current state
        print("\nChecking current database state...")
        check_table_state(conn, "platform_users")
        check_foreign_keys(conn, "platform_users")
        check_table_state(conn, "client_companies")
        check_foreign_keys(conn, "client_companies")
        
        # Clean up any failed migration artifacts
        print("\nCleaning up failed migration artifacts...")
        cleanup_failed_migration(conn, "platform_users")
        cleanup_failed_migration(conn, "client_companies")
        
        # Migration order (tables without foreign keys first)
        migration_steps = [
            # Step 1: Migrate platform_users (no foreign keys)
            ("platform_users", None),
            
            # Step 2: Migrate client_companies (has foreign key to platform_users)
            ("client_companies", {"platform_user_id": "platform_users"}),
            
            # Step 3: Migrate other tables
            ("client_app_users", None),
            ("events", {"client_company_id": "client_companies"}),
            ("web3_events", {"client_company_id": "client_companies"}),
            ("platform_metrics", {"client_company_id": "client_companies"}),
        ]
        
        # Phase 1: Add UUID columns and update foreign keys
        print("\nPhase 1: Adding UUID columns and updating foreign keys...")
        for table_name, foreign_keys in migration_steps:
            if not migrate_table_with_foreign_keys(conn, table_name, foreign_keys):
                print(f"Phase 1 failed for {table_name}")
                return False
        
        # Phase 2: Finalize migration by swapping columns
        print("\nPhase 2: Finalizing migration...")
        for table_name, foreign_keys in migration_steps:
            if not finalize_migration(conn, table_name, foreign_keys):
                print(f"Phase 2 failed for {table_name}")
                return False
        
        print("\nUUID migration completed successfully!")
        print("Your database now uses UUIDs for all ID columns.")
        
        # Verify final state
        print("\nVerifying final database state...")
        check_table_state(conn, "platform_users")
        check_table_state(conn, "client_companies")
        
    except Exception as e:
        print(f"Migration fix failed: {e}")
        return False
    finally:
        conn.close()
        print("Database connection closed")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
