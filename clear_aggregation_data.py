#!/usr/bin/env python3
"""Clear all aggregation data before re-migration."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

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

def clear_aggregation_data():
    """Clear all aggregation-related data."""
    print("🗑️ Clearing All Aggregation Data")
    print("=" * 50)
    
    # Get Heroku database connection
    engine = get_heroku_db_connection()
    
    # Create session
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Get counts before clearing
        raw_events_count = db.query(models.RawEvent).count()
        daily_count = db.query(models.CampaignAnalyticsDaily).count()
        hourly_count = db.query(models.CampaignAnalyticsHourly).count()
        subscription_plans_count = db.query(models.SubscriptionPlan).count()
        
        print(f"📊 Current data counts:")
        print(f"   Raw Events: {raw_events_count}")
        print(f"   Daily Aggregations: {daily_count}")
        print(f"   Hourly Aggregations: {hourly_count}")
        print(f"   Subscription Plans: {subscription_plans_count}")
        
        # Clear in order (respecting foreign key constraints)
        print("\n🗑️ Clearing data...")
        
        # 1. Clear hourly aggregations first (they might reference daily)
        if hourly_count > 0:
            db.query(models.CampaignAnalyticsHourly).delete()
            print(f"   ✅ Cleared {hourly_count} hourly aggregations")
        
        # 2. Clear daily aggregations
        if daily_count > 0:
            db.query(models.CampaignAnalyticsDaily).delete()
            print(f"   ✅ Cleared {daily_count} daily aggregations")
        
        # 3. Clear raw events
        if raw_events_count > 0:
            db.query(models.RawEvent).delete()
            print(f"   ✅ Cleared {raw_events_count} raw events")
        
        # 4. Clear subscription plans
        if subscription_plans_count > 0:
            db.query(models.SubscriptionPlan).delete()
            print(f"   ✅ Cleared {subscription_plans_count} subscription plans")
        
        # Commit all changes
        db.commit()
        
        # Verify clearing
        raw_events_after = db.query(models.RawEvent).count()
        daily_after = db.query(models.CampaignAnalyticsDaily).count()
        hourly_after = db.query(models.CampaignAnalyticsHourly).count()
        subscription_plans_after = db.query(models.SubscriptionPlan).count()
        
        print(f"\n📊 After clearing:")
        print(f"   Raw Events: {raw_events_after}")
        print(f"   Daily Aggregations: {daily_after}")
        print(f"   Hourly Aggregations: {hourly_after}")
        print(f"   Subscription Plans: {subscription_plans_after}")
        
        if (raw_events_after == 0 and daily_after == 0 and 
            hourly_after == 0 and subscription_plans_after == 0):
            print("\n✅ SUCCESS: All aggregation data cleared!")
            return True
        else:
            print("\n❌ FAILURE: Some data was not cleared")
            return False
            
    except Exception as e:
        print(f"❌ Error clearing data: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def main():
    """Main clearing process."""
    print("🚀 Clear Aggregation Data")
    print("=" * 50)
    
    # Check if running on Heroku
    if os.getenv('DYNO'):
        print("✅ Running on Heroku")
    else:
        print("⚠️ Not running on Heroku - make sure DATABASE_URL is set")
    
    # Clear data
    success = clear_aggregation_data()
    
    if success:
        print("\n🎉 Aggregation data cleared successfully!")
        print("🚀 Ready for fresh migration!")
    else:
        print("\n❌ Failed to clear aggregation data!")
        sys.exit(1)

if __name__ == "__main__":
    main()
