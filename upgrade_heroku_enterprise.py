#!/usr/bin/env python3
"""
Upgrade all companies to Enterprise subscription plan on Heroku.
This script is designed to run on Heroku with proper environment handling.
"""

import os
import sys
import traceback
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

# Import the database session directly from the app
from app.database import SessionLocal
from app.models import SubscriptionPlan, ClientCompany
import uuid

def upgrade_all_to_enterprise_heroku():
    """Upgrade all companies to Enterprise subscription plan on Heroku."""
    
    print("🚀 Heroku Enterprise Plan Upgrade")
    print("=" * 50)
    
    try:
        print(f"🔗 Connecting to Heroku database...")
        
        # Use the app's database session directly
        db = SessionLocal()
        
        # Get all companies
        companies = db.query(ClientCompany).all()
        
        if not companies:
            print("⚠️ No companies found in the database.")
            return False
        
        print(f"📊 Found {len(companies)} companies to upgrade")
        print()
        
        enterprise_plan_config = {
            "plan_name": "enterprise",
            "plan_tier": 3,
            "raw_data_retention_days": 90,
            "aggregation_frequency": "real_time",
            "max_raw_events_per_month": 10000000,
            "max_aggregated_rows_per_month": 2000000,
            "monthly_price_usd": 499.0
        }
        
        upgraded_count = 0
        created_count = 0
        updated_count = 0
        
        for company in companies:
            print(f"🏢 Processing: {company.name} (ID: {company.id})")
            
            # Check if company already has a subscription plan
            existing_plan = db.query(SubscriptionPlan).filter(
                SubscriptionPlan.company_id == company.id
            ).first()
            
            if existing_plan:
                # Update existing plan to Enterprise
                print(f"   📝 Updating {existing_plan.plan_name} → Enterprise")
                existing_plan.plan_name = enterprise_plan_config["plan_name"]
                existing_plan.plan_tier = enterprise_plan_config["plan_tier"]
                existing_plan.raw_data_retention_days = enterprise_plan_config["raw_data_retention_days"]
                existing_plan.aggregation_frequency = enterprise_plan_config["aggregation_frequency"]
                existing_plan.max_raw_events_per_month = enterprise_plan_config["max_raw_events_per_month"]
                existing_plan.max_aggregated_rows_per_month = enterprise_plan_config["max_aggregated_rows_per_month"]
                existing_plan.monthly_price_usd = enterprise_plan_config["monthly_price_usd"]
                existing_plan.updated_at = datetime.now()
                updated_count += 1
            else:
                # Create new Enterprise plan
                print(f"   ✨ Creating new Enterprise plan")
                new_plan = SubscriptionPlan(
                    company_id=company.id,
                    **enterprise_plan_config
                )
                db.add(new_plan)
                created_count += 1
            
            upgraded_count += 1
            print(f"   ✅ Success")
        
        # Commit all changes
        db.commit()
        
        print(f"\n🎉 Upgrade Complete!")
        print(f"   📊 Companies processed: {upgraded_count}")
        print(f"   ✨ New plans: {created_count}")
        print(f"   📝 Updated plans: {updated_count}")
        
        # Verify the upgrades
        enterprise_plans = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.plan_name == "enterprise"
        ).all()
        
        print(f"✅ Verification: {len(enterprise_plans)} Enterprise plans active")
        
        db.close()
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
