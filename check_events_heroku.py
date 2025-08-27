#!/usr/bin/env python3
"""Debug script to check events table structure on Heroku."""

import os
import psycopg2
from urllib.parse import urlparse

def check_events():
    """Check the events table structure and data."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found")
        return
    
    try:
        parsed = urlparse(database_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password
        )
        
        with conn.cursor() as cursor:
            # Check events table
            cursor.execute("SELECT id, event_name, client_company_id FROM events LIMIT 5")
            events = cursor.fetchall()
            
            print("📊 EVENTS TABLE SAMPLE:")
            print("=" * 50)
            for event in events:
                print(f"Event ID: {event[0]}")
                print(f"Name: {event[1]}")
                print(f"Company ID: {event[2]} (Type: {type(event[2]).__name__})")
                print("-" * 30)
            
            # Check company IDs
            cursor.execute("SELECT id, name FROM client_companies LIMIT 3")
            companies = cursor.fetchall()
            
            print("\n🏢 COMPANIES TABLE SAMPLE:")
            print("=" * 50)
            for company in companies:
                print(f"Company ID: {company[0]} (Type: {type(company[0]).__name__})")
                print(f"Name: {company[1]}")
                print("-" * 30)
            
            # Check if there's a mismatch
            print("\n🔍 CHECKING FOR MISMATCHES:")
            print("=" * 50)
            
            # Get all event company IDs
            cursor.execute("SELECT DISTINCT client_company_id FROM events")
            event_company_ids = [str(row[0]) for row in cursor.fetchall()]
            
            # Get all company IDs
            cursor.execute("SELECT id FROM client_companies")
            company_ids = [str(row[0]) for row in cursor.fetchall()]
            
            print(f"Event company IDs: {event_company_ids[:5]}...")
            print(f"Company IDs: {company_ids[:5]}...")
            
            # Check for orphaned events
            orphaned_events = [eid for eid in event_company_ids if eid not in company_ids]
            if orphaned_events:
                print(f"❌ Found {len(orphaned_events)} orphaned events with invalid company IDs")
                print(f"Orphaned IDs: {orphaned_events[:5]}...")
            else:
                print("✅ All events have valid company IDs")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_events()
