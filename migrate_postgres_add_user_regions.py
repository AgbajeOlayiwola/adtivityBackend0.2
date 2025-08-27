#!/usr/bin/env python3
"""PostgreSQL migration script to add missing columns to client_app_users table."""

import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from sqlalchemy import create_engine, text

def migrate_postgres_client_app_users():
    """Add missing columns to client_app_users table on PostgreSQL."""
    print("🔧 POSTGRESQL MIGRATION: client_app_users TABLE")
    print("=" * 60)
    
    # Get DATABASE_URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not found")
        print("💡 Set it with: export DATABASE_URL='your_heroku_postgresql_url'")
        return
    
    print(f"🔗 Connecting to: {database_url[:50]}...")
    
    # Create database engine
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        try:
            # Check if columns already exist
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'client_app_users'
            """))
            existing_columns = [row[0] for row in result]
            
            print(f"📋 Existing columns: {existing_columns}")
            
            # Columns to add with proper PostgreSQL types
            columns_to_add = [
                ("region", "VARCHAR(100)"),
                ("city", "VARCHAR(100)"), 
                ("company_id", "UUID"),
                ("platform_user_id", "UUID"),
                ("user_id", "VARCHAR")
            ]
            
            # Add missing columns
            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    sql = f"ALTER TABLE client_app_users ADD COLUMN {column_name} {column_type}"
                    print(f"➕ Adding column: {column_name} ({column_type})")
                    conn.execute(text(sql))
                    conn.commit()
                    print(f"✅ Added column: {column_name}")
                else:
                    print(f"✅ Column already exists: {column_name}")
            
            print("\n🎉 PostgreSQL migration completed successfully!")
            
            # Show final schema
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'client_app_users'
                ORDER BY ordinal_position
            """))
            
            print("\n📊 Final table schema:")
            print("-" * 60)
            for row in result:
                print(f"  {row[0]}: {row[1]} (nullable: {row[2]})")
                    
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()

if __name__ == "__main__":
    migrate_postgres_client_app_users()
