#!/usr/bin/env python3
"""Migrate Web3 events to aggregation system."""

import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.core.aggregation_service import AggregationService
from app import models

def get_heroku_db_connection():
    """Get Heroku database connection."""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        raise ValueError("DATABASE_URL not found. Make sure you're running on Heroku or have DATABASE_URL set.")
    
    # Convert postgres:// to postgresql:// for SQLAlchemy
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    # Create engine with connection pooling for Heroku
    engine = create_engine(
        database_url,
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"}
    )
    
    return engine

def migrate_web3_events():
    """Migrate Web3 events to aggregation system."""
    print("🔗 Migrating Web3 events to aggregation system...")
    
    # Get Heroku database connection
    engine = get_heroku_db_connection()
    
    # Create session
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Get Web3 events
        web3_events = db.query(models.Web3Event).all()
        print(f"📊 Found {len(web3_events)} Web3 events to migrate")
        
        if len(web3_events) == 0:
            print("ℹ️ No Web3 events found to migrate")
            return True
        
        # Initialize aggregation service
        aggregation_service = AggregationService(db)
        
        migrated_count = 0
        error_count = 0
        
        for event in web3_events:
            try:
                # Convert to aggregation format (Web3Event has different fields)
                event_data = {
                    "campaign_id": "heroku_web3_migration",
                    "event_name": event.event_name,
                    "event_type": "web3_event",
                    "user_id": event.user_id,
                    "anonymous_id": None,  # Web3Event doesn't have this field
                    "session_id": None,    # Web3Event doesn't have this field
                    "properties": event.properties or {},
                    "country": None,       # Web3Event doesn't have location fields
                    "region": None,
                    "city": None,
                    "ip_address": None,
                    "timestamp": event.timestamp or datetime.now(timezone.utc),
                    "wallet_address": event.wallet_address,
                    "chain_id": event.chain_id
                }
                
                # Process through aggregation system
                asyncio.run(aggregation_service.process_event(
                    str(event.client_company_id), 
                    event_data
                ))
                migrated_count += 1
                
                if migrated_count % 5 == 0:
                    print(f"   Migrated {migrated_count}/{len(web3_events)} Web3 events...")
                    
            except Exception as e:
                print(f"   ⚠️ Error migrating Web3 event {event.id}: {e}")
                error_count += 1
                continue
        
        print(f"✅ Successfully migrated {migrated_count} Web3 events")
        if error_count > 0:
            print(f"⚠️ {error_count} Web3 events failed to migrate")
        
        # Verify migration
        raw_events_count = db.query(models.RawEvent).count()
        daily_count = db.query(models.CampaignAnalyticsDaily).count()
        hourly_count = db.query(models.CampaignAnalyticsHourly).count()
        
        print(f"\n📊 Current aggregation data:")
        print(f"   Raw Events: {raw_events_count}")
        print(f"   Daily Aggregations: {daily_count}")
        print(f"   Hourly Aggregations: {hourly_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Web3 Events Migration to Aggregation System")
    print("=" * 50)
    
    # Check if running on Heroku
    if os.getenv('DYNO'):
        print("✅ Running on Heroku")
    else:
        print("⚠️ Not running on Heroku - make sure DATABASE_URL is set")
    
    # Run migration
    success = migrate_web3_events()
    
    if success:
        print("\n🎉 Web3 events migration completed!")
        print("🚀 Your aggregation system now includes Web3 events!")
    else:
        print("\n❌ Web3 events migration failed!")
        sys.exit(1)
