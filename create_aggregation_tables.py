#!/usr/bin/env python3
"""Create aggregation tables for tiered data storage."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models import Base

def create_aggregation_tables():
    """Create the aggregation tables in the database."""
    
    # Database connection
    database_url = settings.DATABASE_URL
    engine = create_engine(database_url)
    
    # Create tables
    print("🔧 Creating aggregation tables...")
    
    # Define the aggregation tables
    aggregation_tables = [
        "raw_events",
        "campaign_analytics_daily", 
        "campaign_analytics_hourly",
        "subscription_plans"
    ]
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine, tables=[
            table for table in Base.metadata.tables.values() 
            if table.name in aggregation_tables
        ])
        
        print("✅ Aggregation tables created successfully!")
        
        # Verify tables exist
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('raw_events', 'campaign_analytics_daily', 'campaign_analytics_hourly', 'subscription_plans')
                ORDER BY table_name
            """))
            
            existing_tables = [row[0] for row in result]
            
            print(f"📊 Tables created: {', '.join(existing_tables)}")
            
            # Show table schemas
            for table_name in existing_tables:
                print(f"\n🔍 Schema for {table_name}:")
                schema_result = conn.execute(text(f"""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position
                """))
                
                for col in schema_result:
                    nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                    default = f" DEFAULT {col[3]}" if col[3] else ""
                    print(f"  - {col[0]}: {col[1]} {nullable}{default}")
        
        print(f"\n🎉 Successfully created {len(existing_tables)} aggregation tables!")
        
        # Create sample subscription plans
        create_sample_plans(engine)
        
    except Exception as e:
        print(f"❌ Error creating aggregation tables: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def create_sample_plans(engine):
    """Create sample subscription plans for demonstration."""
    
    print("\n📋 Creating sample subscription plans...")
    
    try:
        with engine.connect() as conn:
            # Check if we have any companies to assign plans to
            company_result = conn.execute(text("SELECT id, name FROM client_companies LIMIT 1"))
            companies = company_result.fetchall()
            
            if not companies:
                print("⚠️ No companies found. Skipping sample plan creation.")
                return
            
            company_id = companies[0][0]
            company_name = companies[0][1]
            
            # Create sample plans
            sample_plans = [
                {
                    "plan_name": "basic",
                    "plan_tier": 1,
                    "raw_data_retention_days": 0,
                    "aggregation_frequency": "daily",
                    "max_raw_events_per_month": 0,
                    "max_aggregated_rows_per_month": 100000,
                    "monthly_price_usd": 0.0
                },
                {
                    "plan_name": "pro", 
                    "plan_tier": 2,
                    "raw_data_retention_days": 7,
                    "aggregation_frequency": "hourly",
                    "max_raw_events_per_month": 1000000,
                    "max_aggregated_rows_per_month": 500000,
                    "monthly_price_usd": 99.0
                },
                {
                    "plan_name": "enterprise",
                    "plan_tier": 3,
                    "raw_data_retention_days": 90,
                    "aggregation_frequency": "real_time",
                    "max_raw_events_per_month": 10000000,
                    "max_aggregated_rows_per_month": 2000000,
                    "monthly_price_usd": 499.0
                }
            ]
            
            for plan in sample_plans:
                # Check if plan already exists
                existing = conn.execute(text("""
                    SELECT id FROM subscription_plans 
                    WHERE company_id = :company_id AND plan_name = :plan_name
                """), {"company_id": company_id, "plan_name": plan["plan_name"]})
                
                if not existing.fetchone():
                    conn.execute(text("""
                        INSERT INTO subscription_plans (
                            company_id, plan_name, plan_tier, raw_data_retention_days,
                            aggregation_frequency, max_raw_events_per_month,
                            max_aggregated_rows_per_month, monthly_price_usd
                        ) VALUES (
                            :company_id, :plan_name, :plan_tier, :raw_data_retention_days,
                            :aggregation_frequency, :max_raw_events_per_month,
                            :max_aggregated_rows_per_month, :monthly_price_usd
                        )
                    """), {**plan, "company_id": company_id})
                    
                    print(f"✅ Created {plan['plan_name']} plan for {company_name}")
                else:
                    print(f"ℹ️ {plan['plan_name']} plan already exists for {company_name}")
            
            conn.commit()
            
    except Exception as e:
        print(f"❌ Error creating sample plans: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Starting Aggregation Tables Creation...")
    print("=" * 50)
    
    success = create_aggregation_tables()
    
    if success:
        print("\n🎉 Aggregation system is ready!")
        print("\n📊 Available API Endpoints:")
        print("  POST   /aggregation/subscriptions/     - Create subscription plan")
        print("  GET    /aggregation/subscriptions/     - Get current plan")
        print("  PUT    /aggregation/subscriptions/     - Update plan")
        print("  POST   /aggregation/events/            - Process event")
        print("  POST   /aggregation/aggregate/         - Trigger aggregation")
        print("  GET    /aggregation/analytics/daily/   - Get daily analytics")
        print("  GET    /aggregation/analytics/hourly/  - Get hourly analytics")
        print("  GET    /aggregation/analytics/raw/     - Get raw events")
        print("  GET    /aggregation/storage/savings/   - Get storage savings")
        print("  POST   /aggregation/cleanup/           - Cleanup expired data")
        
        print("\n💡 Usage Examples:")
        print("  1. Set company to Pro plan for hourly analytics")
        print("  2. Send events via /aggregation/events/")
        print("  3. View aggregated analytics via /analytics/daily/ or /analytics/hourly/")
        print("  4. Monitor storage savings via /storage/savings/")
        
    else:
        print("\n❌ Failed to create aggregation tables!")
        sys.exit(1)
