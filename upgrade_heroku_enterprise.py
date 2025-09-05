#!/usr/bin/env python3
"""
Upgrade all companies to Enterprise subscription plan on Heroku.
This script is designed to run on Heroku with proper environment handling.
"""

import sys
import os
import traceback
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.models import SubscriptionPlan, ClientCompany
import uuid

def upgrade_all_to_enterprise_heroku():
    """Upgrade all companies to Enterprise subscription plan on Heroku."""
    
    print("🚀 Heroku Enterprise Plan Upgrade")
    print("=" * 50)
    
    try:
        print(f"🔗 Connecting to Heroku database...")
        
        # Database connection using raw SQL like other working scripts
        database_url = settings.DATABASE_URL
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Get all companies
            companies_result = conn.execute(text("SELECT id, name FROM client_companies"))
            companies = companies_result.fetchall()
            
            if not companies:
                print("⚠️ No companies found in the database.")
                return False
            
            print(f"📊 Found {len(companies)} companies to upgrade")
            print()
            
            upgraded_count = 0
            created_count = 0
            updated_count = 0
            
            for company_id, company_name in companies:
                print(f"🏢 Processing: {company_name} (ID: {company_id})")
                
                # Check if company already has a subscription plan
                existing_plan_result = conn.execute(text("""
                    SELECT id, plan_name FROM subscription_plans 
                    WHERE company_id = :company_id
                """), {"company_id": company_id})
                existing_plan = existing_plan_result.fetchone()
                
                if existing_plan:
                    # Update existing plan to Enterprise
                    print(f"   📝 Updating {existing_plan[1]} → Enterprise")
                    conn.execute(text("""
                        UPDATE subscription_plans SET
                            plan_name = 'enterprise',
                            plan_tier = 3,
                            raw_data_retention_days = 90,
                            aggregation_frequency = 'real_time',
                            max_raw_events_per_month = 10000000,
                            max_aggregated_rows_per_month = 2000000,
                            monthly_price_usd = 499.0,
                            updated_at = NOW()
                        WHERE company_id = :company_id
                    """), {"company_id": company_id})
                    updated_count += 1
                else:
                    # Create new Enterprise plan
                    print(f"   ✨ Creating new Enterprise plan")
                    conn.execute(text("""
                        INSERT INTO subscription_plans (
                            id, company_id, plan_name, plan_tier, 
                            raw_data_retention_days, aggregation_frequency,
                            max_raw_events_per_month, max_aggregated_rows_per_month,
                            monthly_price_usd, created_at, updated_at
                        ) VALUES (
                            gen_random_uuid(), :company_id, 'enterprise', 3,
                            90, 'real_time', 10000000, 2000000,
                            499.0, NOW(), NOW()
                        )
                    """), {"company_id": company_id})
                    created_count += 1
                
                upgraded_count += 1
                print(f"   ✅ Success")
            
            # Commit all changes
            conn.commit()
            
            print(f"\n🎉 Upgrade Complete!")
            print(f"   📊 Companies processed: {upgraded_count}")
            print(f"   ✨ New plans: {created_count}")
            print(f"   📝 Updated plans: {updated_count}")
            
            # Verify the upgrades
            enterprise_result = conn.execute(text("""
                SELECT COUNT(*) FROM subscription_plans 
                WHERE plan_name = 'enterprise'
            """))
            enterprise_count = enterprise_result.fetchone()[0]
            
            print(f"✅ Verification: {enterprise_count} Enterprise plans active")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = upgrade_all_to_enterprise_heroku()
    
    if success:
        print("\n🚀 All companies upgraded to Enterprise!")
        print("💡 Benefits now active:")
        print("   - Real-time data processing")
        print("   - 90 days raw data retention")
        print("   - 10M events/month capacity")
        print("   - Full analytics capabilities")
    else:
        print("\n❌ Upgrade failed!")
        sys.exit(1)
