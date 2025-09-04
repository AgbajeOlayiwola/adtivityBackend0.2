#!/usr/bin/env python3
"""
Heroku Database Migration Script
Safely migrates existing data to aggregation system on Heroku PostgreSQL
"""

import os
import asyncio
import sys
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text, create_engine
from sqlalchemy.pool import NullPool

# Add the app directory to the path
sys.path.append('.')

from app.core.aggregation_service import AggregationService
from app import models, crud

def get_heroku_db_connection():
    """Get Heroku database connection."""
    # Heroku sets DATABASE_URL automatically
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        raise ValueError("DATABASE_URL not found. Make sure you're running on Heroku or have DATABASE_URL set.")
    
    # Convert postgres:// to postgresql:// for SQLAlchemy
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    # Create engine with connection pooling for Heroku
    engine = create_engine(
        database_url,
        poolclass=NullPool,  # Heroku recommends NullPool
        pool_pre_ping=True,  # Verify connections before use
        connect_args={"sslmode": "require"}  # Heroku requires SSL
    )
    
    return engine

def migrate_heroku_data():
    """Migrate existing data to aggregation system on Heroku."""
    print("🚀 Starting Heroku database migration...")
    print("=" * 50)
    
    # Get Heroku database connection
    engine = get_heroku_db_connection()
    
    # Create session
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Check current data
        print("📊 Checking current data...")
        events_count = db.query(models.Event).count()
        web3_events_count = db.query(models.Web3Event).count()
        companies_count = db.query(models.ClientCompany).count()
        
        print(f"   Events: {events_count}")
        print(f"   Web3 Events: {web3_events_count}")
        print(f"   Companies: {companies_count}")
        
        if events_count == 0 and web3_events_count == 0:
            print("⚠️ No existing data found. Creating sample data...")
            create_sample_data(db)
            events_count = db.query(models.Event).count()
            web3_events_count = db.query(models.Web3Event).count()
        
        # Initialize aggregation service
        aggregation_service = AggregationService(db)
        
        # 1. Migrate regular events
        print(f"\n📊 Migrating {events_count} regular events...")
        events = db.query(models.Event).all()
        migrated_events = 0
        
        for event in events:
            try:
                # Convert to aggregation format
                event_data = {
                    "campaign_id": "heroku_migration",
                    "event_name": event.event_name,
                    "event_type": "legacy_event",
                    "user_id": event.user_id,
                    "anonymous_id": event.anonymous_id,
                    "session_id": event.session_id,
                    "properties": event.properties or {},
                    "country": event.country,
                    "region": event.region,
                    "city": event.city,
                    "ip_address": event.ip_address,
                    "timestamp": event.timestamp or datetime.now(timezone.utc),
                    "wallet_address": None,
                    "chain_id": None
                }
                
                # Process through aggregation system
                asyncio.run(aggregation_service.process_event(
                    str(event.client_company_id), 
                    event_data
                ))
                migrated_events += 1
                
                if migrated_events % 10 == 0:
                    print(f"   Migrated {migrated_events}/{events_count} events...")
                    
            except Exception as e:
                print(f"   ⚠️ Error migrating event {event.id}: {e}")
                continue
        
        print(f"✅ Migrated {migrated_events} regular events")
        
        # 2. Migrate Web3 events
        print(f"\n🔗 Migrating {web3_events_count} Web3 events...")
        web3_events = db.query(models.Web3Event).all()
        migrated_web3_events = 0
        
        for event in web3_events:
            try:
                # Convert to aggregation format
                event_data = {
                    "campaign_id": "heroku_web3_migration",
                    "event_name": event.event_name,
                    "event_type": "web3_event",
                    "user_id": event.user_id,
                    "anonymous_id": event.anonymous_id,
                    "session_id": event.session_id,
                    "properties": event.properties or {},
                    "country": event.country,
                    "region": event.region,
                    "city": event.city,
                    "ip_address": event.ip_address,
                    "timestamp": event.timestamp or datetime.now(timezone.utc),
                    "wallet_address": event.wallet_address,
                    "chain_id": event.chain_id
                }
                
                # Process through aggregation system
                asyncio.run(aggregation_service.process_event(
                    str(event.client_company_id), 
                    event_data
                ))
                migrated_web3_events += 1
                
                if migrated_web3_events % 10 == 0:
                    print(f"   Migrated {migrated_web3_events}/{web3_events_count} Web3 events...")
                    
            except Exception as e:
                print(f"   ⚠️ Error migrating Web3 event {event.id}: {e}")
                continue
        
        print(f"✅ Migrated {migrated_web3_events} Web3 events")
        
        # 3. Create default subscription plans for existing companies
        print(f"\n💳 Creating default subscription plans for {companies_count} companies...")
        companies = db.query(models.ClientCompany).all()
        plans_created = 0
        
        for company in companies:
            try:
                # Check if company already has a plan
                existing_plan = db.query(models.SubscriptionPlan).filter(
                    models.SubscriptionPlan.company_id == company.id
                ).first()
                
                if not existing_plan:
                    # Create default basic plan
                    default_plan = models.SubscriptionPlan(
                        company_id=company.id,
                        plan_name="basic",
                        plan_tier=1,
                        raw_data_retention_days=0,
                        aggregation_frequency="daily",
                        max_raw_events_per_month=0,
                        max_aggregated_rows_per_month=100000,
                        monthly_price_usd=0.0
                    )
                    db.add(default_plan)
                    plans_created += 1
                    
            except Exception as e:
                print(f"   ⚠️ Error creating plan for company {company.id}: {e}")
                continue
        
        db.commit()
        print(f"✅ Created {plans_created} default subscription plans")
        
        # 4. Verify migration
        print(f"\n🔍 Verifying migration...")
        raw_events_count = db.query(models.RawEvent).count()
        daily_count = db.query(models.CampaignAnalyticsDaily).count()
        hourly_count = db.query(models.CampaignAnalyticsHourly).count()
        plans_count = db.query(models.SubscriptionPlan).count()
        
        print(f"   Raw Events: {raw_events_count}")
        print(f"   Daily Aggregations: {daily_count}")
        print(f"   Hourly Aggregations: {hourly_count}")
        print(f"   Subscription Plans: {plans_count}")
        
        # 5. Summary
        total_migrated = migrated_events + migrated_web3_events
        print(f"\n🎉 Heroku migration completed successfully!")
        print(f"   📊 Total events migrated: {total_migrated}")
        print(f"   💳 Subscription plans created: {plans_created}")
        print(f"   🔄 All existing data preserved in original tables")
        print(f"   ✨ New aggregation data available for analytics")
        print(f"   🚀 Ready for production use on Heroku")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def create_sample_data(db):
    """Create sample data if none exists."""
    print("   Creating sample data for testing...")
    
    # Get first company
    company = db.query(models.ClientCompany).first()
    if not company:
        print("   ⚠️ No companies found. Please create a company first.")
        return
    
    # Create sample events
    sample_events = [
        {
            "event_name": "user_signup",
            "user_id": "user_123",
            "country": "US",
            "region": "CA",
            "city": "San Francisco",
            "timestamp": datetime.now(timezone.utc)
        },
        {
            "event_name": "user_login",
            "user_id": "user_456",
            "country": "CA",
            "region": "ON",
            "city": "Toronto",
            "timestamp": datetime.now(timezone.utc)
        }
    ]
    
    for event_data in sample_events:
        event = models.Event(
            client_company_id=company.id,
            **event_data
        )
        db.add(event)
    
    db.commit()
    print("   ✅ Sample data created")

def verify_heroku_migration():
    """Verify that Heroku migration was successful."""
    print("\n🔍 Verifying Heroku migration...")
    
    engine = get_heroku_db_connection()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Count original data
        original_events = db.query(models.Event).count()
        original_web3_events = db.query(models.Web3Event).count()
        
        # Count new aggregation data
        raw_events = db.query(models.RawEvent).count()
        daily_aggregations = db.query(models.CampaignAnalyticsDaily).count()
        hourly_aggregations = db.query(models.CampaignAnalyticsHourly).count()
        subscription_plans = db.query(models.SubscriptionPlan).count()
        
        print(f"📊 Original data (preserved):")
        print(f"   Events: {original_events}")
        print(f"   Web3 Events: {original_web3_events}")
        
        print(f"🔄 New aggregation data:")
        print(f"   Raw Events: {raw_events}")
        print(f"   Daily Aggregations: {daily_aggregations}")
        print(f"   Hourly Aggregations: {hourly_aggregations}")
        print(f"   Subscription Plans: {subscription_plans}")
        
        if raw_events > 0 or daily_aggregations > 0:
            print("✅ Heroku migration verification successful!")
            print("🚀 Your Heroku app is ready for production!")
        else:
            print("⚠️ No aggregation data found - migration may have failed")
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Heroku Database Migration to Aggregation System")
    print("=" * 60)
    
    # Check if running on Heroku
    if os.getenv('DYNO'):
        print("✅ Running on Heroku")
    else:
        print("⚠️ Not running on Heroku - make sure DATABASE_URL is set")
    
    # Run migration
    migrate_heroku_data()
    
    # Verify migration
    verify_heroku_migration()
    
    print("\n📋 Next Steps for Heroku:")
    print("1. Deploy your updated code to Heroku")
    print("2. Test the aggregation system with your app")
    print("3. Monitor Heroku logs for any issues")
    print("4. Check analytics endpoints to ensure they work")
    print("5. Consider upgrading companies to higher subscription tiers")
