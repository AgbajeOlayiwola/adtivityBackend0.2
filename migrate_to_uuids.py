#!/usr/bin/env python3
"""
Migration script to convert all integer IDs to UUIDs for enhanced security.
This prevents enumeration attacks and makes it harder to guess valid IDs.
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

def backup_table(conn, table_name):
    """Create a backup of the table before migration."""
    cursor = conn.cursor()
    backup_table_name = f"{table_name}_backup_{int(uuid.uuid4().hex[:8], 16)}"
    
    try:
        cursor.execute(f"CREATE TABLE {backup_table_name} AS SELECT * FROM {table_name}")
        conn.commit()
        print(f"Created backup table: {backup_table_name}")
        return backup_table_name
    except Exception as e:
        print(f"Failed to create backup for {table_name}: {e}")
        conn.rollback()
        return None

def add_uuid_columns(conn, table_name, id_column="id"):
    """Add UUID columns to the table."""
    cursor = conn.cursor()
    
    try:
        # Add new UUID column
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {id_column}_uuid UUID")
        print(f"Added UUID column to {table_name}")
        
        # Generate UUIDs for existing records
        cursor.execute(f"UPDATE {table_name} SET {id_column}_uuid = gen_random_uuid()")
        print(f"Generated UUIDs for existing records in {table_name}")
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Failed to add UUID column to {table_name}: {e}")
        conn.rollback()
        return False

def update_foreign_keys(conn, table_name, foreign_key_column, referenced_table):
    """Update foreign key references to use UUIDs."""
    cursor = conn.cursor()
    
    try:
        # Get the foreign key constraint name
        cursor.execute(f"""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = '{table_name}' 
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name LIKE '%{foreign_key_column}%'
        """)
        
        constraint_result = cursor.fetchone()
        if constraint_result:
            constraint_name = constraint_result[0]
            
            # Drop the foreign key constraint
            cursor.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name}")
            print(f"Dropped foreign key constraint: {constraint_name}")
            
            # Add new foreign key constraint with UUID
            cursor.execute(f"""
                ALTER TABLE {table_name} 
                ADD CONSTRAINT {constraint_name}_uuid 
                FOREIGN KEY ({foreign_key_column}_uuid) 
                REFERENCES {referenced_table}(id_uuid)
            """)
            print(f"Added new UUID foreign key constraint for {table_name}")
            
        conn.commit()
        return True
    except Exception as e:
        print(f"Failed to update foreign keys for {table_name}: {e}")
        conn.rollback()
        return False

def swap_columns(conn, table_name, id_column="id"):
    """Swap the old integer column with the new UUID column."""
    cursor = conn.cursor()
    
    try:
        # Drop the old integer column
        cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN {id_column}")
        print(f"Dropped old integer column from {table_name}")
        
        # Rename UUID column to the original name
        cursor.execute(f"ALTER TABLE {table_name} RENAME COLUMN {id_column}_uuid TO {id_column}")
        print(f"Renamed UUID column in {table_name}")
        
        # Make the UUID column the primary key
        cursor.execute(f"ALTER TABLE {table_name} ADD PRIMARY KEY ({id_column})")
        print(f"Set UUID column as primary key in {table_name}")
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Failed to swap columns in {table_name}: {e}")
        conn.rollback()
        return False

def migrate_table(conn, table_name, foreign_keys=None):
    """Migrate a single table from integer IDs to UUIDs."""
    print(f"\nMigrating table: {table_name}")
    
    # Create backup
    backup_table_name = backup_table(conn, table_name)
    if not backup_table_name:
        return False
    
    # Add UUID columns
    if not add_uuid_columns(conn, table_name):
        return False
    
    # Update foreign keys if specified
    if foreign_keys:
        for fk_column, ref_table in foreign_keys.items():
            if not update_foreign_keys(conn, table_name, fk_column, ref_table):
                return False
    
    # Swap columns
    if not swap_columns(conn, table_name):
        return False
    
    print(f"Successfully migrated table: {table_name}")
    return True

def main():
    """Main migration function."""
    print("Starting UUID Migration for Enhanced Security")
    print("=" * 60)
    
    # Connect to database
    conn = connect_to_database()
    print("Connected to database successfully")
    
    try:
        # Define migration order (tables without foreign keys first)
        migration_order = [
            # Tables without foreign keys
            ("platform_users", None),
            
            # Tables with foreign keys
            ("client_companies", {"platform_user_id": "platform_users"}),
            ("client_app_users", None),
            ("events", {"client_company_id": "client_companies"}),
            ("web3_events", {"client_company_id": "client_companies"}),
            ("platform_metrics", {"client_company_id": "client_companies"}),
        ]
        
        # Execute migrations
        for table_name, foreign_keys in migration_order:
            if not migrate_table(conn, table_name, foreign_keys):
                print(f"Migration failed for {table_name}")
                return False
        
        print("\nAll tables migrated successfully!")
        print("Your application now uses UUIDs for enhanced security!")
        print("Remember to update your application code to handle UUIDs")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        return False
    finally:
        conn.close()
        print("Database connection closed")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
